"""Tests for Program, ProgramTask, and ProgramEnrollment models."""
import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import Club, User, Contact, Planner
from app.models.program import Program, ProgramTask, ProgramEnrollment


def test_program_creation(app, default_club):
    """Test Program creation and its fields."""
    with app.app_context():
        # Create a user to act as creator
        creator = User(username="admin_user", email="admin@example.com")
        creator.set_password("password")
        db.session.add(creator)
        db.session.commit()

        program = Program(
            club_id=default_club.id,
            name="New Member Orientation",
            description="Orientation program for new members",
            is_active=True,
            display_order=1,
            created_by_id=creator.id
        )
        db.session.add(program)
        db.session.commit()

        assert program.id is not None
        assert program.club_id == default_club.id
        assert program.name == "New Member Orientation"
        assert program.description == "Orientation program for new members"
        assert program.is_active is True
        assert program.display_order == 1
        assert program.created_by_id == creator.id
        assert isinstance(program.created_at, datetime)
        assert isinstance(program.updated_at, datetime)
        assert repr(program) == f'<Program New Member Orientation (id={program.id})>'


def test_program_task_ordering_and_cascade(app, default_club):
    """Test ProgramTask fields, reordering, and cascade delete from Program."""
    with app.app_context():
        program = Program(
            club_id=default_club.id,
            name="Test Program"
        )
        db.session.add(program)
        db.session.commit()

        # Add tasks with different display_orders
        task2 = ProgramTask(
            program_id=program.id,
            title="Task B",
            display_order=10,
            completion_type="manual"
        )
        task1 = ProgramTask(
            program_id=program.id,
            title="Task A",
            display_order=5,
            completion_type="ice_breaker",
            is_required=True
        )
        db.session.add_all([task2, task1])
        db.session.commit()

        # Verify default values and types
        assert task1.id is not None
        assert task1.completion_type == "ice_breaker"
        assert task1.is_required is True

        # Verify ordering in program relationship
        db.session.refresh(program)
        assert len(program.tasks) == 2
        assert program.tasks[0].title == "Task A"  # display_order = 5
        assert program.tasks[1].title == "Task B"  # display_order = 10

        # Verify cascade delete
        task_id = task1.id
        db.session.delete(program)
        db.session.commit()

        assert db.session.get(ProgramTask, task_id) is None


def test_program_enrollment_constraints_and_cascade(app, default_club):
    """Test ProgramEnrollment fields, unique constraint, and planner cascade delete."""
    with app.app_context():
        program = Program(
            club_id=default_club.id,
            name="Enrollment Test Program"
        )
        task = ProgramTask(
            title="Task 1",
            completion_type="manual"
        )
        program.tasks.append(task)
        db.session.add(program)
        db.session.commit()

        # Create mentee and mentor
        mentee = User(username="mentee_user", email="mentee@example.com")
        mentee.set_password("password")
        mentor = User(username="mentor_user", email="mentor@example.com")
        mentor.set_password("password")
        db.session.add_all([mentee, mentor])
        db.session.commit()

        mentor_contact = Contact(Name="Mentor Name", Type="Member", Email="mentor@example.com")
        db.session.add(mentor_contact)
        db.session.commit()

        # Create enrollment
        enrollment = ProgramEnrollment(
            program_id=program.id,
            user_id=mentee.id,
            mentor_user_id=mentor.id,
            mentor_contact_id=mentor_contact.id,
            club_id=default_club.id,
            status="active",
            notes="Initial notes"
        )
        db.session.add(enrollment)
        db.session.commit()

        assert enrollment.id is not None
        assert enrollment.status == "active"
        assert enrollment.notes == "Initial notes"
        assert enrollment.mentor_user_id == mentor.id
        assert enrollment.mentor_contact_id == mentor_contact.id

        # Verify UniqueConstraint(program_id, user_id, club_id)
        duplicate_enrollment = ProgramEnrollment(
            program_id=program.id,
            user_id=mentee.id,
            club_id=default_club.id,
            status="active"
        )
        db.session.add(duplicate_enrollment)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

        # Create a planner entry linked to the enrollment
        planner_entry = Planner(
            user_id=mentee.id,
            club_id=default_club.id,
            enrollment_id=enrollment.id,
            program_task_id=task.id,
            status="draft"
        )
        db.session.add(planner_entry)
        db.session.commit()

        # Verify relationship backref
        assert enrollment.planner_entries.count() == 1
        assert planner_entry.enrollment == enrollment

        # Verify cascade delete of Planner when Enrollment is deleted
        planner_id = planner_entry.id
        db.session.delete(enrollment)
        db.session.commit()

        assert db.session.get(Planner, planner_id) is None
