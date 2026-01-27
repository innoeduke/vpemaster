from app import db
from app.models import SessionLog, SessionType, Waitlist, Roster, MeetingRole, Contact, Meeting, OwnerMeetingRoles
from datetime import datetime, timezone
from sqlalchemy import or_

class RoleService:
    @staticmethod
    def assign_meeting_role(session_log, contact_ids, is_admin=False, replace_contact_id=None):
        """
        Assigns contact(s) to a session log (and related logs if role is not distinct).
        
        Args:
            session_log: The SessionLog object to update
            contact_ids: ID or List of IDs of the new owner(s) (or None to unassign)
            is_admin: Boolean indicating if action is performed by an admin
            replace_contact_id: For shared roles, the ID of the owner being replaced
            
        Returns:
            list: List of updated SessionLog objects
        """
        if not session_log:
            return []
            
        # Normalize to list
        if contact_ids is None:
            contact_ids = []
        if isinstance(contact_ids, int):
            contact_ids = [contact_ids]
        
        # For shared roles with replace_contact_id, modify the existing owner list
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None
        
        if replace_contact_id and role_obj and not role_obj.has_single_owner:
            # Get current owners and replace the specific one
            current_owners = [o.id for o in session_log.owners]
            if replace_contact_id in current_owners:
                # Replace the old owner with the new one
                new_owner_list = [cid for cid in current_owners if cid != replace_contact_id]
                if contact_ids:
                    new_owner_list.extend(contact_ids)
                contact_ids = new_owner_list

        # Delegate everything to the internal helper which handles Model updates, Roster Sync, AND Waitlist clearing
        return RoleService._captured_assign_role(session_log, contact_ids, is_admin)

    @staticmethod
    def _captured_assign_role(session_log, contact_ids, is_admin=False):
        """
        Internal helper that wraps set_owners with Roster syncing.
        """
        if contact_ids is None:
            contact_ids = []
        if isinstance(contact_ids, int):
            contact_ids = [contact_ids]
            
        # Capture old owner(s) - usually all related logs have same owner if valid
        # We need to capture ALL owners for roster cleanup
        # Assuming fetch of owners happens or we rely on session_log.owners
        old_owners = list(session_log.owners)
        old_owner_ids = [c.id for c in old_owners]
        
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None

        # 1. Clear Waitlists for the new owners (if assigned)
        if contact_ids:
            # Find related sessions & remove these users from waitlist for this role group
            related_session_ids = RoleService._get_related_session_ids(session_log)
            Waitlist.query.filter(
                Waitlist.session_log_id.in_(related_session_ids),
                Waitlist.contact_id.in_(contact_ids)
            ).delete(synchronize_session=False)

        # Call Model Update
        updated_logs = SessionLog.set_owners(session_log, contact_ids)
        
        # Sync Roster
        if role_obj:
            # 1. Unassign Old Owners (if existed and not in new list)
            for old_id in old_owner_ids:
                if old_id not in contact_ids:
                    Roster.sync_role_assignment(session_log.Meeting_Number, old_id, role_obj, 'unassign')
            
            # 2. Assign New Owners (if exists)
            for new_id in contact_ids:
                Roster.sync_role_assignment(session_log.Meeting_Number, new_id, role_obj, 'assign')
        
        # Invalidate Cache
        RoleService._clear_meeting_cache(session_log.Meeting_Number)
                
        return updated_logs

    @staticmethod
    def _clear_meeting_cache(meeting_number, club_id=None):
        """
        Invalidates all cached data related to a meeting's roles and role-takers.
        """
        from app import cache
        from app.club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        # 1. Clear Meeting Roles (consolidated for booking)
        if club_id:
            cache.delete(f"meeting_roles_{club_id}_{meeting_number}")
        cache.delete(f"meeting_roles_None_{meeting_number}") # Fallback
        
        # 2. Clear Role Takers (mapped by person for voting/roster)
        if club_id:
            cache.delete(f"role_takers_{club_id}_{meeting_number}")
        cache.delete(f"role_takers_None_{meeting_number}") # Fallback

    @staticmethod
    def book_meeting_role(session_log, user_contact_id):
        """
        Handles self-booking logic: Checks duplicates, approvals, then assigns.
        """
        if not session_log:
            return False, "Session not found."

        # 1. Duplicate Check
        if RoleService.check_duplicates(session_log, user_contact_id):
             return False, "Warning: You have already booked a role of this type for this meeting."

        # 2. Approval Check
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None
        
        if role_obj and role_obj.needs_approval:
            return RoleService.join_waitlist(session_log, user_contact_id)

        # 3. Validation: Is it already taken?
        # IMPORTANT: Self-booking strictly implies claiming an EMPTY slot.
        # If there are existing owners, self-booking usually shouldn't behave as "join team" unless explicit.
        # Current logic checks if owners are set.
        if session_log.owners:
             return RoleService.join_waitlist(session_log, user_contact_id)

        # 4. Success -> Assign
        RoleService._captured_assign_role(session_log, [user_contact_id])
        db.session.commit()
        return True, "Role booked successfully."

    @staticmethod
    def cancel_meeting_role(session_log, contact_id, is_admin=False):
        """
        Handles cancellation. If user is owner -> remove. If on waitlist -> remove.
        Auto-promotes waitlist if owner cancels.
        """
        if not session_log:
            return False, "Session not found."

        # Check if user is on waitlist
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_log.id, contact_id=contact_id).first()
        
        if waitlist_entry:
            db.session.delete(waitlist_entry)
            db.session.commit()
            
            # Invalidate Cache
            RoleService._clear_meeting_cache(session_log.Meeting_Number)
                
            return True, "Removed from waitlist."

        # Check if user is an owner
        is_owner = False
        current_owner_ids = [c.id for c in session_log.owners]
        if contact_id in current_owner_ids or is_admin:
             is_owner = True
        
        if is_owner:
             # Unassign ONLY this user
             # If there were multiple owners, keep the others.
             new_owner_ids = [oid for oid in current_owner_ids if oid != contact_id]
             
             RoleService._captured_assign_role(session_log, new_owner_ids)
             
             # Auto-promote logic
             # Only auto-promote if the slot becomes COMPLETEY empty?
             # Or if we want to fill the spot immediately?
             # Standard logic: if it becomes empty, try to fill.
             if not new_owner_ids:
                 session_type = session_log.session_type
                 role_obj = session_type.role if session_type else None
                 
                 if role_obj and not role_obj.needs_approval:
                     # Check for waitlist
                     next_in_line = Waitlist.query.filter_by(session_log_id=session_log.id)\
                         .order_by(Waitlist.timestamp.asc()).first()
                     
                     if next_in_line:
                         # Promote
                         promoted_id = next_in_line.contact_id
                         db.session.delete(next_in_line) # Remove from waitlist
                         RoleService._captured_assign_role(session_log, [promoted_id])
                         return True, "Booking cancelled. Next user on waitlist has been promoted."
            
             db.session.commit()
             return True, "Booking cancelled."
        
        return False, "You do not hold this role."

    @staticmethod
    def join_waitlist(session_log, contact_id):
        # Handle 'distinct' roles vs grouped roles waitlisting
        session_ids = RoleService._get_related_session_ids(session_log)
        
        # Check total limit (Owners + Waitlist) <= 4
        # We check the first session log since they are grouped
        target_log = SessionLog.query.get(session_ids[0]) if session_ids else session_log
        owner_count = len(target_log.owners)
        
        # Count distinct contact_ids in waitlist for related sessions
        existing_waitlist_contacts = db.session.query(Waitlist.contact_id)\
            .filter(Waitlist.session_log_id.in_(session_ids))\
            .distinct().count()
            
        if (owner_count + existing_waitlist_contacts) >= 4:
            return False, "Waitlist full (Max 4 total participants)."

        added = False
        for s_id in session_ids:
            exists = Waitlist.query.filter_by(session_log_id=s_id, contact_id=contact_id).first()
            if not exists:
                wl = Waitlist(session_log_id=s_id, contact_id=contact_id, timestamp=datetime.now(timezone.utc))
                db.session.add(wl)
                added = True
        
        if added:
            db.session.commit()
            
            # Invalidate Cache
            RoleService._clear_meeting_cache(session_log.Meeting_Number)
            
            return True, "Added to waitlist."
        return True, "Already on waitlist." # Treated as success

    @staticmethod
    def leave_waitlist(session_log, contact_id):
        session_ids = RoleService._get_related_session_ids(session_log)
        
        Waitlist.query.filter(
            Waitlist.session_log_id.in_(session_ids), 
            Waitlist.contact_id == contact_id
        ).delete(synchronize_session=False)
        
        db.session.commit()
        db.session.commit()
        
        # Invalidate Cache
        RoleService._clear_meeting_cache(session_log.Meeting_Number)
             
        return True, "Removed from waitlist."

    @staticmethod
    def approve_waitlist(session_log):
        # Find top waitlist entry
        wl_entry = Waitlist.query.filter_by(session_log_id=session_log.id).order_by(Waitlist.timestamp.asc()).first()
        if not wl_entry:
            return False, "No one on the waitlist."
        
        contact_id = wl_entry.contact_id
        
        # Get current owners and role info
        current_owner_ids = [c.id for c in session_log.owners]
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None
        
        # If currently empty -> Set as owner
        if not current_owner_ids:
            RoleService._captured_assign_role(session_log, [contact_id])
        else:
            # If role supports multiple owners (shared role), append to existing owners
            if role_obj and not role_obj.has_single_owner:
                new_owner_list = current_owner_ids + [contact_id]
                RoleService._captured_assign_role(session_log, new_owner_list)
            else:
                # Single-owner role: Replace the current owner
                RoleService._captured_assign_role(session_log, [contact_id])

        db.session.commit()
        
        return True, "Waitlist approved."

    @staticmethod
    def check_duplicates(session_log, contact_id):
        """
        Check if contact_id already has a role of this type in this meeting.
        """
        session_type = session_log.session_type
        if not session_type or not session_type.role_id:
            return False
            
        current_role_id = session_type.role_id
        
        # Check specific exclusion logic if needed (e.g. allowing double roles for some types)
        # For now, standard check:
        existing = db.session.query(SessionLog.id)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
            .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
            .filter(SessionLog.Meeting_Number == session_log.Meeting_Number)\
            .filter(db.exists().where(
                db.and_(
                    OwnerMeetingRoles.contact_id == contact_id,
                    OwnerMeetingRoles.meeting_id == Meeting.id,
                    OwnerMeetingRoles.role_id == MeetingRole.id,
                    db.or_(
                        OwnerMeetingRoles.session_log_id == SessionLog.id,
                        OwnerMeetingRoles.session_log_id.is_(None)
                    )
                )
            ))\
            .filter(SessionType.role_id == current_role_id)\
            .filter(SessionLog.id != session_log.id)\
            .first()
            
        return existing is not None

    @staticmethod
    def _get_related_session_ids(session_log):
        """
        Helper to find all session IDs that should be treated as a group 
        (e.g. for non-distinct roles like Speakers, waitlist applies to all slots).
        """
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None
        
        if role_obj and role_obj.has_single_owner:
            return [session_log.id]
            
        # If not distinct, find all sessions with same role in this meeting
        # Use simple query
        if not role_obj:
            return [session_log.id]
            
        logs = db.session.query(SessionLog.id)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .filter(SessionLog.Meeting_Number == session_log.Meeting_Number)\
            .filter(SessionType.role_id == role_obj.id)\
            .all()
            
        return [l.id for l in logs]

    @staticmethod
    def get_meeting_roles(meeting_number, club_id=None):
        """
        Get all roles for a meeting, consolidated for booking page display.
        
        Roles with has_single_owner=True: Each session log becomes its own slot.
        Roles with has_single_owner=False: All session logs of that role type are 
        consolidated into a single record (shared role).
        
        Args:
            meeting_number: The meeting number to query
            club_id: Optional club ID filter
            
        Returns:
            list: List of role dictionaries ready for booking page display
        """
        from app import cache
        from app.club_context import get_current_club_id
        from sqlalchemy.orm import joinedload, subqueryload
        
        if not club_id:
            club_id = get_current_club_id()
            
        if not meeting_number:
            return []

        # Check Cache
        cache_key = f"meeting_roles_{club_id}_{meeting_number}"
        cached_roles = cache.get(cache_key)
        if cached_roles is not None:
            return cached_roles

        # Query session logs with eager loading
        query = db.session.query(SessionLog)\
            .options(
                joinedload(SessionLog.session_type).joinedload(SessionType.role),
                joinedload(SessionLog.meeting),
                subqueryload(SessionLog.waitlists).joinedload(Waitlist.contact)
            )\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
            .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
            .filter(SessionLog.Meeting_Number == meeting_number)\
            .filter(MeetingRole.name != '', MeetingRole.name.isnot(None))
        
        if club_id:
            query = query.filter(Meeting.club_id == club_id)
            
        session_logs = query.all()
        
        # Consolidate roles
        roles_dict = {}
        
        # Track which roles we've processed as shared
        shared_roles_processed = set()
        roles_list = []

        for log in session_logs:
            if not log.session_type or not log.session_type.role:
                continue
                
            role_obj = log.session_type.role
            role_id = role_obj.id
            has_single_owner = role_obj.has_single_owner
            
            if has_single_owner:
                # One slot per session log
                owner = log.owner
                roles_list.append({
                    'role': role_obj.name.strip(),
                    'role_id': role_id,
                    'owner_id': owner.id if owner else None,
                    'owner_name': owner.Name if owner else None,
                    'owner_avatar_url': owner.Avatar_URL if owner else None,
                    'session_id': log.id,
                    'icon': role_obj.icon,
                    'is_member_only': role_obj.is_member_only,
                    'needs_approval': role_obj.needs_approval,
                    'award_category': role_obj.award_category,
                    'has_single_owner': True,
                    'speaker_name': log.Session_Title.strip() if role_obj.name.strip() == "Individual Evaluator" and log.Session_Title else None,
                    'waitlist': [
                        {
                            'name': w.contact.Name,
                            'id': w.contact_id,
                            'avatar_url': w.contact.Avatar_URL
                        } for w in log.waitlists
                    ]
                })
            else:
                # Shared role: Group all owners across all session logs of this type
                if role_id in shared_roles_processed:
                    continue
                shared_roles_processed.add(role_id)
                
                # Get all session logs for this shared role to consolidate waitlists
                related_logs = [l for l in session_logs if l.session_type.role_id == role_id]
                first_log = related_logs[0]
                
                # Consolidate waitlists across all related logs
                seen_waitlist_ids = set()
                consolidated_waitlist = []
                for l in related_logs:
                    for w in l.waitlists:
                        if w.contact_id not in seen_waitlist_ids:
                            consolidated_waitlist.append({
                                'name': w.contact.Name,
                                'id': w.contact_id,
                                'avatar_url': w.contact.Avatar_URL
                            })
                            seen_waitlist_ids.add(w.contact_id)
                
                # Get all owners for this shared role (all session logs share the same owners)
                all_owners = first_log.owners
                
                # Create ONE record for the shared role
                roles_list.append({
                    'role': role_obj.name.strip(),
                    'role_id': role_id,
                    'owner_id': None, # Populated contextually in route
                    'owner_name': None,
                    'owner_avatar_url': None,
                    'all_owners': [
                        {
                            'id': o.id,
                            'name': o.Name,
                            'avatar_url': o.Avatar_URL
                        } for o in all_owners
                    ],
                    'session_id': first_log.id,
                    'icon': role_obj.icon,
                    'is_member_only': role_obj.is_member_only,
                    'needs_approval': role_obj.needs_approval,
                    'award_category': role_obj.award_category,
                    'has_single_owner': False,
                    'waitlist': consolidated_waitlist
                })
        
        # Cache the result
        cache.set(cache_key, roles_list)
        
        return roles_list

    @staticmethod
    def get_role_takers(meeting_number, club_id=None):
        """
        Get all role takers for a meeting from OwnerMeetingRoles.
        
        Returns a map of contact_id -> [role_data] showing which roles
        each contact has taken in the meeting.
        
        Args:
            meeting_number: The meeting number to query
            club_id: Optional club ID filter
            
        Returns:
            dict: Map of contact_id (str) -> list of role dictionaries
        """
        from app import cache
        from app.club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        if not meeting_number:
            return {}

        # Check Cache
        cache_key = f"role_takers_{club_id}_{meeting_number}"
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Query OwnerMeetingRoles joined with Meeting and MeetingRole
        query = db.session.query(OwnerMeetingRoles, MeetingRole, Contact)\
            .join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
            .outerjoin(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
            .join(Contact, OwnerMeetingRoles.contact_id == Contact.id)\
            .filter(Meeting.Meeting_Number == meeting_number)
        
        if club_id:
            query = query.filter(Meeting.club_id == club_id)
            
        results = query.all()
        
        # Build map: contact_id -> [roles]
        role_takers = {}
        for omr, role, contact in results:
            c_id = str(contact.id)
            role_data = {
                'id': role.id if role else None,
                'name': role.name if role else "N/A",
                'icon': role.icon if role else None,
                'award_category': role.award_category.strip() if role and role.award_category else "",
                'session_log_id': omr.session_log_id,
                'owner_name': contact.Name,
                'owner_avatar_url': contact.Avatar_URL
            }
            if c_id not in role_takers:
                role_takers[c_id] = []
            # Avoid duplicates
            if role_data not in role_takers[c_id]:
                role_takers[c_id].append(role_data)
        
        # Cache the result
        cache.set(cache_key, role_takers)
        
        return role_takers
    @staticmethod
    def get_roles_for_contact(contact_id, club_id=None):
        """
        Retrieves all role duties assigned to a specific contact.
        This includes both single-owner and shared roles across meetings.
        This serves as the source of truth for a user's activity logs.
        
        Args:
            contact_id: ID of the contact to query
            club_id: Optional club ID to filter meetings
            
        Returns:
            list: List of SessionLog objects, with context_owner attached.
        """
        from app.models import OwnerMeetingRoles, Meeting, MeetingRole, SessionLog, SessionType, Contact
        
        # 1. Query OwnerMeetingRoles entries for this contact
        query = db.session.query(OwnerMeetingRoles, Meeting, MeetingRole, Contact)\
            .join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
            .outerjoin(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
            .join(Contact, OwnerMeetingRoles.contact_id == Contact.id)\
            .filter(OwnerMeetingRoles.contact_id == contact_id)
            
        if club_id:
            query = query.filter(Meeting.club_id == club_id)
            
        results = query.order_by(Meeting.Meeting_Number.desc()).all()
        
        # 2. Map to SessionLogs
        logs = []
        for omr, meeting, role, contact in results:
            log = None
            if omr.session_log_id:
                # Use query to allow eager loading of relationships
                log = SessionLog.query.filter_by(id=omr.session_log_id).options(
                    db.joinedload(SessionLog.meeting),
                    db.joinedload(SessionLog.session_type).joinedload(SessionType.role),
                    db.joinedload(SessionLog.project)
                ).first()
            elif role:
                # Shared role: Find the relevant session log for this meeting/role type
                log = SessionLog.query.join(SessionType).filter(
                    SessionLog.Meeting_Number == meeting.Meeting_Number,
                    SessionType.role_id == role.id
                ).options(
                    db.joinedload(SessionLog.meeting),
                    db.joinedload(SessionLog.session_type).joinedload(SessionType.role),
                    db.joinedload(SessionLog.project)
                ).first()
                
            if log:
                # Ensure the log knows its context-specific owner for display
                log.context_owner = contact
                # Attach credential from OwnerMeetingRole
                log.context_credential = omr.credential
                logs.append(log)
                
        return logs
