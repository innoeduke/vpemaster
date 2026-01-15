from app import db
from app.models import SessionLog, SessionType, Waitlist, Roster, MeetingRole, Contact, Meeting
from app.constants import SessionTypeID
from datetime import datetime, timezone
from sqlalchemy import or_

class RoleService:
    @staticmethod
    def assign_meeting_role(session_log, contact_id, is_admin=False):
        """
        Assigns a contact to a session log (and related logs if role is not distinct).
        
        Args:
            session_log: The SessionLog object to update
            contact_id: ID of the new owner (or None to unassign)
            is_admin: Boolean indicating if action is performed by an admin
            
        Returns:
            list: List of updated SessionLog objects
        """
        if not session_log:
            return []

        # Delegate everything to the internal helper which handles Model updates, Roster Sync, AND Waitlist clearing
        return RoleService._captured_assign_role(session_log, contact_id, is_admin)

    @staticmethod
    def _captured_assign_role(session_log, contact_id, is_admin=False):
        """
        Internal helper that wraps set_owner with Roster syncing.
        """
        # Capture old owner(s) - usually all related logs have same owner if valid
        old_owner_id = session_log.Owner_ID
        
        session_type = session_log.session_type
        role_obj = session_type.role if session_type else None

        # 1. Clear Waitlists for the new owner (if assigned)
        if contact_id:
            # Find related sessions & remove this user from waitlist for this role group
            related_session_ids = RoleService._get_related_session_ids(session_log)
            Waitlist.query.filter(
                Waitlist.session_log_id.in_(related_session_ids),
                Waitlist.contact_id == contact_id
            ).delete(synchronize_session=False)

        # Call Model Update
        updated_logs = SessionLog.set_owner(session_log, contact_id)
        
        # Sync Roster
        if role_obj:
            # 1. Unassign Old Owner (if existed and different)
            if old_owner_id and old_owner_id != contact_id:
                Roster.sync_role_assignment(session_log.Meeting_Number, old_owner_id, role_obj, 'unassign')
            
            # 2. Assign New Owner (if exists)
            if contact_id:
                Roster.sync_role_assignment(session_log.Meeting_Number, contact_id, role_obj, 'assign')
                
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
        if session_log.Owner_ID:
             return RoleService.join_waitlist(session_log, user_contact_id)

        # 4. Success -> Assign
        RoleService._captured_assign_role(session_log, user_contact_id)
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
            return True, "Removed from waitlist."

        # Check if user is owner
        if session_log.Owner_ID == contact_id or is_admin:
             # Unassign
             RoleService._captured_assign_role(session_log, None)
             
             # Auto-promote from waitlist logic could go here
             # For now, we'll leave it empty (no auto-promote) to match existing behavior 
             # unless user specifically requested auto-promote in plan (Plan said 'Check Waitlist -> Auto-promote next')
             
             # Let's check if there is a waitlist to promote
             # But usually we want manual approval or the user to claim it.
             # Existing code in booking_routes.py:368 just set owner_id_to_set = None.
             # But WAIT, `_handle_cancel` in plan mentions: "Returns owner_id (likely None or next waitlisted user)."
             
             # Let's implement auto-promote if the role does NOT require approval
             session_type = session_log.session_type
             role_obj = session_type.role if session_type else None
             
             if role_obj and not role_obj.needs_approval:
                 # Check for waitlist
                 next_in_line = Waitlist.query.filter_by(session_log_id=session_log.id)\
                     .order_by(Waitlist.timestamp.asc()).first()
                 
                 if next_in_line:
                     # Promote
                     new_owner_id = next_in_line.contact_id
                     db.session.delete(next_in_line) # Remove from waitlist
                     RoleService._captured_assign_role(session_log, new_owner_id)
                     db.session.commit()
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
        return True, "Removed from waitlist."

    @staticmethod
    def approve_waitlist(session_log):
        # Find top waitlist entry
        wl_entry = Waitlist.query.filter_by(session_log_id=session_log.id).order_by(Waitlist.timestamp.asc()).first()
        if not wl_entry:
            return False, "No one on the waitlist."
        
        contact_id = wl_entry.contact_id
        
        # Assign (which handles clearing waitlist for the new owner)
        RoleService._captured_assign_role(session_log, contact_id)
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
            .filter(SessionLog.Owner_ID == contact_id)\
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
