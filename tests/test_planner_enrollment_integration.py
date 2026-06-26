"""Integration tests for planner program enrollment, auto-detection triggers, and meeting completions."""
import pytest
from datetime import datetime, timezone, date
from app import db
from app.models import Club, User, Contact, UserClub, SessionLog, SessionType, Project, Planner, Meeting
from app.models.roster import MeetingRole
from app.models.session import OwnerMeetingRoles
from app.models.program import Program, ProgramTask, ProgramEnrollment
from app.services.planner_service import planner_service


@pytest.fixture
def integration_setup(app, default_club):
    """Set up a test program with different task completion types and a test member."""
    with app.app_context():
        # Create program template
        program = Program(
            club_id=default_club.id,
            name="Onboarding Integration Program"
        )
        db.session.add(program)
        db.session.flush()

        # Create a Timer role to get its ID for role completion type task
        role_timer = MeetingRole.query.filter_by(name="Timer", club_id=None).first()
        if not role_timer:
            role_timer = MeetingRole(name="Timer", type="Standard", needs_approval=False, has_single_owner=True)
            db.session.add(role_timer)
            db.session.flush()

        # Add tasks
        task_manual = ProgramTask(
            program_id=program.id,
            title="Manual Task",
            completion_type="manual",
            display_order=1
        )
        task_pathway = ProgramTask(
            program_id=program.id,
            title="Select Pathway",
            completion_type="path",
            completion_config={"path_ids": [1]},
            display_order=2
        )
        task_mentor = ProgramTask(
            program_id=program.id,
            title="Assign Mentor",
            completion_type="field",
            completion_config={"field": "mentor_id"},
            display_order=3
        )
        task_icebreaker = ProgramTask(
            program_id=program.id,
            title="Deliver Ice Breaker",
            completion_type="project",
            completion_config={"project_ids": [101]},
            display_order=4
        )
        task_sessionlog = ProgramTask(
            program_id=program.id,
            title="Serve as Timer",
            completion_type="role",
            completion_config={"role_ids": [role_timer.id]},
            display_order=5
        )
        db.session.add_all([task_manual, task_pathway, task_mentor, task_icebreaker, task_sessionlog])
        db.session.commit()

        # Create mentee/member
        user = User(username="integration_member", email="integration@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        contact = Contact(Name="Integration Contact", Type="Member", Email="integration@example.com")
        db.session.add(contact)
        db.session.flush()

        uc = UserClub(user_id=user.id, club_id=default_club.id, contact_id=contact.id)
        db.session.add(uc)
        db.session.commit()

    return {
        "program_id": program.id,
        "user_id": user.id,
        "contact_id": contact.id
    }


def test_enrollment_seeding_and_auto_detection(app, default_club, integration_setup):
    """Test that creating an enrollment seeds tasks and runs auto-detection rules."""
    with app.app_context():
        program = db.session.get(Program, integration_setup["program_id"])
        user = db.session.get(User, integration_setup["user_id"])
        contact = db.session.get(Contact, integration_setup["contact_id"])

        # 1. Create enrollment when member has no pathway or mentor assigned
        enrollment = planner_service.create_enrollment(
            program=program,
            user_id=user.id,
            club_id=default_club.id
        )

        db.session.refresh(enrollment)
        planner_rows = Planner.query.filter_by(enrollment_id=enrollment.id).all()
        assert len(planner_rows) == 5

        # Check that all are initially draft / incomplete
        for row in planner_rows:
            assert row.status == "draft"
            assert row.auto_completed is False

        # 2. Assign pathway and mentor, then trigger bulk_refresh
        uc = UserClub.query.filter_by(user_id=user.id, club_id=default_club.id).first()
        uc.current_path_id = 1  # Fake ID
        uc.mentor_id = 999  # Fake contact ID
        contact.Mentor_ID = 999
        db.session.commit()

        planner_service.bulk_refresh(enrollment)

        # Check status of pathway and mentor tasks
        row_pathway = Planner.query.filter_by(enrollment_id=enrollment.id, program_task_id=program.tasks[1].id).first()
        row_mentor = Planner.query.filter_by(enrollment_id=enrollment.id, program_task_id=program.tasks[2].id).first()

        assert row_pathway.status == "completed"
        assert row_pathway.auto_completed is True
        assert row_mentor.status == "completed"
        assert row_mentor.auto_completed is True


def test_meeting_completion_triggers(app, default_club, integration_setup):
    """Test that finalizing a meeting triggers auto-detection for speaker/role tasks."""
    with app.app_context():
        program = db.session.get(Program, integration_setup["program_id"])
        user = db.session.get(User, integration_setup["user_id"])
        contact = db.session.get(Contact, integration_setup["contact_id"])

        # Create enrollment
        enrollment = planner_service.create_enrollment(
            program=program,
            user_id=user.id,
            club_id=default_club.id
        )

        # Setup meeting and session logs
        meeting = Meeting(
            club_id=default_club.id,
            Meeting_Number=1,
            Meeting_Date=date(2026, 6, 22),
            status="unpublished"
        )
        db.session.add(meeting)
        db.session.flush()

        # Ice Breaker Project
        project = Project.query.filter_by(Project_Name="Ice Breaker").first()
        if not project:
            project = Project(id=101, Project_Name="Ice Breaker")
            db.session.add(project)
            db.session.flush()

        role_speaker = MeetingRole.query.filter_by(name="Speaker", club_id=None).first()
        if not role_speaker:
            role_speaker = MeetingRole(name="Speaker", type="Standard", needs_approval=False, has_single_owner=False)
            db.session.add(role_speaker)
            db.session.flush()

        role_timer = MeetingRole.query.filter_by(name="Timer", club_id=None).first()
        if not role_timer:
            role_timer = MeetingRole(name="Timer", type="Standard", needs_approval=False, has_single_owner=True)
            db.session.add(role_timer)
            db.session.flush()

        # Setup session types
        st_speech = SessionType(
            club_id=default_club.id,
            Title="Prepared Speech",
            role_id=role_speaker.id,
            Duration_Min=5,
            Duration_Max=7
        )
        st_timer = SessionType(
            club_id=default_club.id,
            Title="Timer",
            role_id=role_timer.id,
            Duration_Min=1,
            Duration_Max=2
        )
        db.session.add_all([st_speech, st_timer])
        db.session.flush()

        # Create Ice Breaker Speech session log (Scheduled)
        log_ib = SessionLog(
            meeting_id=meeting.id,
            Project_ID=project.id,
            Type_ID=st_speech.id,
            Status="Scheduled"
        )
        db.session.add(log_ib)
        db.session.flush()

        owner_ib = OwnerMeetingRoles(
            session_log_id=log_ib.id,
            contact_id=contact.id,
            role_id=role_speaker.id
        )
        db.session.add(owner_ib)

        # Create Timer role session log (Scheduled)
        log_timer = SessionLog(
            meeting_id=meeting.id,
            Type_ID=st_timer.id,
            Status="Scheduled"
        )
        db.session.add(log_timer)
        db.session.flush()

        owner_timer = OwnerMeetingRoles(
            session_log_id=log_timer.id,
            contact_id=contact.id,
            role_id=role_timer.id
        )
        db.session.add(owner_timer)
        db.session.commit()

        # Evaluate should still be incomplete since meeting/logs are Scheduled (not Completed)
        planner_service.bulk_refresh(enrollment)
        row_ib = Planner.query.filter_by(enrollment_id=enrollment.id, program_task_id=program.tasks[3].id).first()
        row_timer = Planner.query.filter_by(enrollment_id=enrollment.id, program_task_id=program.tasks[4].id).first()

        assert row_ib.status == "draft"
        assert row_timer.status == "draft"

        # Complete the logs
        log_ib.Status = "Completed"
        log_timer.Status = "Completed"
        db.session.commit()

        # Evaluate again
        planner_service.bulk_refresh(enrollment)
        db.session.refresh(row_ib)
        db.session.refresh(row_timer)

        assert row_ib.status == "completed"
        assert row_ib.auto_completed is True
        assert row_timer.status == "completed"
        assert row_timer.auto_completed is True
