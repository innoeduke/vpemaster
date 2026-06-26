"""Service layer for Planner and Program operations."""
from datetime import datetime, timezone
from app import db
from app.models import Planner, Program, ProgramTask, ProgramEnrollment, User, Contact, UserClub, SessionLog, Project, Pathway, PathwayProject
from app.models.roster import MeetingRole
from app.models.session import OwnerMeetingRoles


class PlannerService:
    # ============================================================================
    # STANDARD PLANNER OPERATIONS
    # ============================================================================

    def create_plan(self, data, user_id, club_id):
        """Create or update a standard meeting-based planner entry."""
        meeting_id = data.get('meeting_id')
        role_id = data.get('meeting_role_id')

        # Check for existing entry to avoid duplicates
        existing = None
        if meeting_id and role_id:
            existing = Planner.query.filter_by(
                user_id=user_id,
                meeting_id=meeting_id,
                meeting_role_id=role_id
            ).first()

        if existing:
            if 'project_id' in data:
                existing.project_id = data.get('project_id')
            if 'pathway' in data:
                existing.pathway = data.get('pathway')
            if 'title' in data:
                existing.title = data.get('title')
            if 'status' in data:
                existing.status = data.get('status')
            if 'notes' in data:
                existing.notes = data.get('notes')

            db.session.commit()
            
            # Invalidate booking cache
            from .role_service import RoleService
            if existing.meeting_id:
                RoleService._clear_meeting_cache(existing.meeting_id, club_id)
                
            return existing, True

        new_plan = Planner(
            meeting_id=meeting_id,
            meeting_role_id=role_id,
            project_id=data.get('project_id'),
            pathway=data.get('pathway'),
            title=data.get('title'),
            status=data.get('status', 'draft'),
            notes=data.get('notes'),
            user_id=user_id,
            club_id=club_id
        )
        db.session.add(new_plan)
        db.session.commit()

        # Invalidate booking cache
        from .role_service import RoleService
        if new_plan.meeting_id:
            RoleService._clear_meeting_cache(new_plan.meeting_id, club_id)

        return new_plan, False

    def update_plan(self, plan_id, data, user_id, club_id):
        """Update an existing planner entry."""
        plan = Planner.query.filter_by(id=plan_id, user_id=user_id).first_or_404()

        if 'meeting_id' in data:
            plan.meeting_id = data['meeting_id']
        if 'meeting_role_id' in data:
            plan.meeting_role_id = data['meeting_role_id']
        if 'project_id' in data:
            plan.project_id = data['project_id']
        if 'pathway' in data:
            plan.pathway = data['pathway']
        if 'title' in data:
            plan.title = data['title']
        if 'notes' in data:
            plan.notes = data['notes']
        if 'status' in data:
            plan.status = data['status']

        db.session.commit()

        # Invalidate booking cache
        from .role_service import RoleService
        if plan.meeting_id:
            RoleService._clear_meeting_cache(plan.meeting_id, club_id)

        return plan

    def cancel_plan(self, plan_id, user_id, club_id):
        """Cancel a plan and remove the user from the meeting if booked."""
        plan = Planner.query.filter_by(id=plan_id, user_id=user_id).first_or_404()

        # 1. Update status to cancelled
        plan.status = 'cancelled'

        # 2. If it was booked/waitlisted, remove from meeting
        if plan.meeting_id and plan.meeting_role_id:
            from app.models.session import SessionLog, SessionType
            from .role_service import RoleService
            
            session_log = SessionLog.query.join(SessionType).filter(
                SessionLog.meeting_id == plan.meeting_id,
                SessionType.role_id == plan.meeting_role_id
            ).first()

            if session_log:
                user = User.query.get(user_id)
                user_contact_id = user.contact_id if user else None
                if user_contact_id:
                    RoleService.cancel_meeting_role(session_log, user_contact_id, is_admin=True)

        db.session.commit()

        # Invalidate booking cache
        from .role_service import RoleService
        if plan.meeting_id:
            RoleService._clear_meeting_cache(plan.meeting_id, club_id)

        return plan

    def delete_plan(self, plan_id, user_id, club_id):
        """Delete a planner entry."""
        plan = Planner.query.filter_by(id=plan_id, user_id=user_id).first_or_404()
        meeting_id = plan.meeting_id
        db.session.delete(plan)
        db.session.commit()

        # Invalidate booking cache
        from .role_service import RoleService
        if meeting_id:
            RoleService._clear_meeting_cache(meeting_id, club_id)

        return True

    # ============================================================================
    # PROGRAM ENROLLMENTS & TASKS OPERATIONS
    # ============================================================================

    def create_enrollment(self, program, user_id, club_id, mentor_user_id=None, mentor_contact_id=None, notes=None):
        """Create program enrollment and seed planner tasks."""
        # Check duplicate first
        existing = ProgramEnrollment.query.filter_by(
            program_id=program.id,
            user_id=user_id,
            club_id=club_id
        ).first()
        if existing:
            raise ValueError("User is already enrolled in this program.")

        enrollment = ProgramEnrollment(
            program_id=program.id,
            user_id=user_id,
            club_id=club_id,
            mentor_user_id=mentor_user_id,
            mentor_contact_id=mentor_contact_id,
            status='active',
            notes=notes,
            started_at=datetime.now(timezone.utc)
        )
        db.session.add(enrollment)
        db.session.flush()  # Hydrate enrollment.id

        # Seed Planner tasks from template
        for task in program.tasks:
            planner_row = Planner(
                user_id=user_id,
                club_id=club_id,
                enrollment_id=enrollment.id,
                program_task_id=task.id,
                status='draft',
                auto_completed=False
            )
            db.session.add(planner_row)

        db.session.commit()

        # Evaluate auto tasks immediately
        self.bulk_refresh(enrollment)

        return enrollment

    def evaluate(self, planner_row, enrollment):
        """Evaluate if an enrollment task trigger is met.

        Supported completion_type values:
          - 'manual'   : no auto-evaluation (user toggles)
          - 'path'     : config {path_ids: [...]} — mentee's current path is any of these
          - 'level'    : config {level: N} — mentee has reached level N or higher
          - 'role'     : config {role_ids: [...]} — mentee has a completed SessionLog for any of these roles
          - 'project'  : config {project_ids: [...]} — mentee has a completed SessionLog for any of these projects
          - 'field'    : config {field: 'member_no'|'dtm'|'officer'|'mentor_id'} — corresponding contact field is truthy
        """
        task = planner_row.program_task
        if not task or task.completion_type == 'manual':
            return False, None, None

        user = enrollment.mentee
        club_id = enrollment.club_id
        now = datetime.now(timezone.utc)

        def _completed_at_from_log(log):
            if log and log.meeting and log.meeting.Meeting_Date:
                return datetime.combine(log.meeting.Meeting_Date, datetime.min.time())
            if log and log.date_modified:
                return log.date_modified
            return now

        def _completed_at_from_contact(contact):
            if contact:
                if hasattr(contact, 'date_modified') and contact.date_modified:
                    return contact.date_modified
                if getattr(contact, 'Date_Created', None):
                    return datetime.combine(contact.Date_Created, datetime.min.time()).replace(tzinfo=timezone.utc)
            return now

        if task.completion_type == 'path':
            config = task.completion_config or {}
            path_ids = set(config.get('path_ids') or [])
            if not path_ids:
                return False, None, None
            uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
            if uc and uc.current_path_id in path_ids:
                return True, (uc.updated_at or now), None
            contact = user.get_contact(club_id)
            if contact and contact.Current_Path:
                names = {p.name for p in Pathway.query.filter(Pathway.id.in_(path_ids)).all()}
                if contact.Current_Path in names:
                    return True, _completed_at_from_contact(contact), None
            return False, None, None

        if task.completion_type == 'level':
            config = task.completion_config or {}
            try:
                required_level = int(config.get('level') or 0)
            except (TypeError, ValueError):
                return False, None, None
            if required_level <= 0:
                return False, None, None
            contact = user.get_contact(club_id)
            if not contact:
                return False, None, None
            uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
            path_id = uc.current_path_id if uc and uc.current_path_id else None
            if not path_id and contact.Current_Path:
                path_obj = Pathway.query.filter_by(name=contact.Current_Path).first()
                path_id = path_obj.id if path_obj else None
            if not path_id:
                return False, None, None
            max_level = db.session.query(db.func.max(PathwayProject.level))\
                .join(SessionLog, SessionLog.Project_ID == PathwayProject.project_id)\
                .join(OwnerMeetingRoles, OwnerMeetingRoles.session_log_id == SessionLog.id)\
                .filter(
                    OwnerMeetingRoles.contact_id == contact.id,
                    PathwayProject.path_id == path_id,
                    SessionLog.Status.in_(['Completed', 'completed']),
                    PathwayProject.level.isnot(None),
                ).scalar() or 0
            if max_level >= required_level:
                return True, _completed_at_from_contact(contact), None
            return False, None, None

        if task.completion_type == 'role':
            config = task.completion_config or {}
            role_ids = set(config.get('role_ids') or [])
            if not role_ids:
                return False, None, None
            contact = user.get_contact(club_id)
            if not contact:
                return False, None, None
            log = db.session.query(SessionLog)\
                .join(OwnerMeetingRoles, OwnerMeetingRoles.session_log_id == SessionLog.id)\
                .filter(
                    OwnerMeetingRoles.contact_id == contact.id,
                    OwnerMeetingRoles.role_id.in_(role_ids),
                    SessionLog.Status.in_(['Completed', 'completed'])
                ).first()
            if log:
                return True, _completed_at_from_log(log), None
            return False, None, None

        if task.completion_type == 'project':
            config = task.completion_config or {}
            project_ids = set(config.get('project_ids') or [])
            if not project_ids:
                return False, None, None
            contact = user.get_contact(club_id)
            if not contact:
                return False, None, None
            log = db.session.query(SessionLog)\
                .join(OwnerMeetingRoles, OwnerMeetingRoles.session_log_id == SessionLog.id)\
                .filter(
                    OwnerMeetingRoles.contact_id == contact.id,
                    SessionLog.Project_ID.in_(project_ids),
                    SessionLog.Status.in_(['Completed', 'completed'])
                ).first()
            if log:
                return True, _completed_at_from_log(log), None
            return False, None, None

        if task.completion_type == 'field':
            config = task.completion_config or {}
            field = config.get('field')
            contact = user.get_contact(club_id)
            if not contact:
                return False, None, None
            completed_at = _completed_at_from_contact(contact)
            if field == 'member_no':
                return bool(contact.Member_ID), completed_at, None
            if field == 'dtm':
                return bool(contact.DTM), completed_at, None
            if field == 'officer':
                return contact.Type == 'Officer', completed_at, None
            if field == 'mentor_id':
                return bool(contact.Mentor_ID), completed_at, None
            return False, None, None

        # Unknown completion_type — treat as not completed
        return False, None, None

    def toggle_task(self, planner_id, actor_user):
        """Toggle a manual program task checkbox."""
        planner_row = Planner.query.get_or_404(planner_id)
        task = planner_row.program_task
        if not task:
            raise ValueError("Not a program task")
        if task.completion_type != 'manual':
            raise ValueError("Cannot toggle non-manual task")

        if planner_row.status == 'completed':
            planner_row.status = 'draft'
            planner_row.completed_at = None
            planner_row.completed_by_id = None
            planner_row.auto_completed = False
        else:
            planner_row.status = 'completed'
            planner_row.completed_at = datetime.now(timezone.utc)
            planner_row.completed_by_id = actor_user.id
            planner_row.auto_completed = False

        db.session.commit()
        return planner_row

    def bulk_refresh(self, enrollment):
        """Re-evaluate all auto-trigger tasks for active enrollment."""
        if enrollment.status != 'active':
            return

        planner_rows = Planner.query.filter_by(enrollment_id=enrollment.id).all()
        changed = False

        for row in planner_rows:
            task = row.program_task
            if not task or task.completion_type == 'manual':
                continue

            completed, completed_at, completed_by_id = self.evaluate(row, enrollment)
            if completed:
                if row.status != 'completed':
                    row.status = 'completed'
                    row.completed_at = completed_at
                    row.completed_by_id = completed_by_id
                    row.auto_completed = True
                    changed = True
            else:
                if row.status == 'completed' and row.auto_completed:
                    row.status = 'draft'
                    row.completed_at = None
                    row.completed_by_id = None
                    row.auto_completed = False
                    changed = True

        if changed:
            db.session.commit()

    def progress(self, enrollment):
        """Calculate progress statistics for an enrollment."""
        planner_rows = Planner.query.filter_by(enrollment_id=enrollment.id).all()
        total = len(planner_rows)
        done = sum(1 for r in planner_rows if r.status == 'completed')

        required_rows = [r for r in planner_rows if r.program_task and r.program_task.is_required]
        required_total = len(required_rows)
        required_done = sum(1 for r in required_rows if r.status == 'completed')

        percent = int((done / total * 100)) if total > 0 else 0

        return {
            'done': done,
            'total': total,
            'required_done': required_done,
            'required_total': required_total,
            'percent': percent
        }


# Global service instance
planner_service = PlannerService()
