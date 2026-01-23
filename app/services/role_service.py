from app import db
from app.models import SessionLog, SessionType, Waitlist, Roster, MeetingRole, Contact, Meeting
from app.constants import SessionTypeID
from datetime import datetime, timezone
from sqlalchemy import or_

class RoleService:
    @staticmethod
    def assign_meeting_role(session_log, contact_ids, is_admin=False):
        """
        Assigns contact(s) to a session log (and related logs if role is not distinct).
        
        Args:
            session_log: The SessionLog object to update
            contact_ids: ID or List of IDs of the new owner(s) (or None to unassign)
            is_admin: Boolean indicating if action is performed by an admin
            
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
        from app import cache
        from app.club_context import get_current_club_id
        club_id = get_current_club_id()
        if club_id:
             cache.delete(f"meeting_roles_{club_id}_{session_log.Meeting_Number}")
        # Also try deleting without club_id if context is missing or ambiguous (fallback)
        cache.delete(f"meeting_roles_None_{session_log.Meeting_Number}")
                
        return updated_logs

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
            from app import cache
            from app.club_context import get_current_club_id
            club_id = get_current_club_id()
            if club_id:
                cache.delete(f"meeting_roles_{club_id}_{session_log.Meeting_Number}")
                
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
        
        added = False
        for s_id in session_ids:
            exists = Waitlist.query.filter_by(session_log_id=s_id, contact_id=contact_id).first()
            if not exists:
                wl = Waitlist(session_log_id=s_id, contact_id=contact_id, timestamp=datetime.now(timezone.utc))
                db.session.add(wl)
                added = True
        
        if added:
            db.session.commit()
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
        from app import cache
        from app.club_context import get_current_club_id
        club_id = get_current_club_id()
        if club_id:
             cache.delete(f"meeting_roles_{club_id}_{session_log.Meeting_Number}")
             
        return True, "Removed from waitlist."

    @staticmethod
    def approve_waitlist(session_log):
        # Find top waitlist entry
        wl_entry = Waitlist.query.filter_by(session_log_id=session_log.id).order_by(Waitlist.timestamp.asc()).first()
        if not wl_entry:
            return False, "No one on the waitlist."
        
        contact_id = wl_entry.contact_id
        
        # New Logic: Add or Replace?
        # Usually approval implies "filling the spot".
        # If spot already has owners (e.g. multi-owner scenario), this might be an "Add" operation?
        # But waitlist is usually for a *blocked* spot.
        # Let's assume standard behavior: Approve -> Becomes Owner. 
        # But if there are *already* owners, do we append or replace?
        # In single-owner world, it replaces (or filled empty).
        # In multi-owner world, waitlist usually implies "I want IN".
        # Let's check existing owners.
        current_owner_ids = [c.id for c in session_log.owners]
        
        # If currently empty -> Set as owner
        if not current_owner_ids:
            RoleService._captured_assign_role(session_log, [contact_id])
        else:
            # If not empty, usually waitlist means "I'm next if someone drops" OR "I want to join".
            # If the role is distinct (e.g. Toastmaster), distinct=True means 1 person usually.
            # But we are adding multi-owner now. 
            # Let's assume 'Approve' from waitlist means "Add to team" if supported, or "Replace" if conflict?
            # Safest bet: If waitlist was joined because it was FULL (or distinct), approval takes the slot.
            # BUT, we changed logic so `set_owners` replaces the list provided.
            # So if we want to APPEND, we must pass [existing + new].
            # However, `approve_waitlist` is admin action.
            # For now, let's treat it as "Take the slot" -> effectively replace if distinct, or append if meant to be shared?
            # Actually, `approve_waitlist` is typically for "Speaker" roles where previous logic was 1-person.
            # Let's stick to "Assign this person".
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
            .filter(SessionLog.Meeting_Number == session_log.Meeting_Number)\
            .filter(SessionLog.owners.any(id=contact_id))\
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
        
        if role_obj and role_obj.is_distinct:
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
