import pytest
from app import db
from app.models import User, Contact, Planner, Meeting, MeetingRole, Club, UserClub
from app.models.session import SessionLog, SessionType, OwnerMeetingRoles
from app.services.role_service import RoleService

def test_planner_title_sync(app, client):
    with app.app_context():
        # Setup data
        club = Club(id=1, club_name="Test Club", club_no="12345")
        db.session.add(club)
        
        user = User(id=1, username="testuser", email="test@example.com", password_hash="dummy")
        db.session.add(user)
        db.session.commit()
        
        # Link user and contact via UserClub
        contact = Contact(id=1, Name="Test Contact")
        db.session.add(contact)
        db.session.commit()

        uc = UserClub(user_id=1, contact_id=1, club_id=1)
        db.session.add(uc)
        db.session.commit()
        
        meeting = Meeting(id=1, Meeting_Number=100, club_id=1)
        db.session.add(meeting)
        db.session.commit()
        
        role = MeetingRole(id=1, name="Prepared Speaker", type="speaker", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        
        st = SessionType(id=1, Title="Prepared Speech", role_id=1, club_id=1)
        db.session.add(st)
        
        from app.models.project import Project
        project = Project(id=1, Project_Name="Ice Breaker", Format="Prepared Speech")
        db.session.add(project)
        db.session.commit()
        
        log = SessionLog(id=1, meeting_id=1, Type_ID=1)
        db.session.add(log)
        db.session.commit()
        
        # Refresh log to ensure relationship is loaded
        db.session.refresh(log)
        print(f"DEBUG_IN_TEST: log.Meeting_Number={log.Meeting_Number}")
        
        # Create planner entry with title
        # Use meeting_id=1, and model logic should find it via meeting_number
        plan = Planner(
            user_id=user.id,
            club_id=1,
            meeting_id=1,
            meeting_role_id=1,
            title="My Awesome Speech",
            status="draft"
        )
        db.session.add(plan)
        db.session.commit()
        
        # Verify that set_owners loads the title from planner
        print(f"DEBUG: Calling set_owners for log1")
        updated_logs = SessionLog.set_owners(log, [contact.id])
        
        assert len(updated_logs) > 0
        print(f"DEBUG: log1 Session_Title={updated_logs[0].Session_Title}")
        assert updated_logs[0].Session_Title == "My Awesome Speech"
        
        # Test with Keynote Speaker
        role2 = MeetingRole(id=2, name="Keynote Speaker", type="speaker", needs_approval=False, has_single_owner=True)
        db.session.add(role2)
        st2 = SessionType(id=2, Title="Keynote Speaker", role_id=2, club_id=1)
        db.session.add(st2)
        log2 = SessionLog(id=2, meeting_id=1, Type_ID=2)
        db.session.add(log2)
        db.session.commit()
        
        db.session.refresh(log2)
        
        plan2 = Planner(
            user_id=user.id,
            club_id=1,
            meeting_id=1,
            meeting_role_id=2,
            title="Important Keynote",
            status="draft"
        )
        db.session.add(plan2)
        db.session.commit()
        
        print(f"DEBUG: Calling set_owners for log2")
        updated_logs2 = SessionLog.set_owners(log2, [contact.id])
        print(f"DEBUG: log2 Session_Title={updated_logs2[0].Session_Title}")
        assert updated_logs2[0].Session_Title == "Important Keynote"

        # Clear previous assignments to avoid duplicate check
        OwnerMeetingRoles.query.filter(OwnerMeetingRoles.contact_id == contact.id).delete()
        db.session.commit()
        
        log3 = SessionLog(id=3, meeting_id=1, Type_ID=1) # Another speaker slot
        db.session.add(log3)
        db.session.commit()
        
        print(f"DEBUG: Calling book_meeting_role for log3")
        success, msg = RoleService.book_meeting_role(log3, contact.id, project_id=1, title="Direct Book Title")
        print(f"DEBUG: book_meeting_role success={success}, msg={msg}")
        assert success
        db.session.refresh(log3)
        assert log3.Project_ID == 1
        assert log3.Session_Title == "Direct Book Title"

        # Test 4: RoleService.join_waitlist saves to Planner
        print("\n--- Test 4: RoleService.join_waitlist saves to Planner ---")
        # Use a role that needs approval or is taken
        log3.owners = [] # Unassign first
        db.session.commit()
        OwnerMeetingRoles.query.filter_by(session_log_id=3).delete()
        db.session.commit()
        
        # Someone else takes it
        other_contact = Contact(id=2, Name="Other")
        db.session.add(other_contact)
        db.session.commit()
        RoleService._captured_assign_role(log3, [2])
        db.session.commit()
        
        # Test user joins waitlist
        # First clear any existing plan for this spec
        Planner.query.filter_by(user_id=user.id, meeting_id=1, meeting_role_id=1).delete()
        db.session.commit()
        
        print(f"DEBUG: Calling join_waitlist for log3")
        success, msg = RoleService.join_waitlist(log3, contact.id, project_id=1, title="Waitlist Title")
        print(f"DEBUG: join_waitlist success={success}, msg={msg}")
        assert success
        
        plan3 = Planner.query.filter_by(user_id=user.id, meeting_id=1, meeting_role_id=1).first()
        assert plan3 is not None
        assert plan3.project_id == 1
        assert plan3.title == "Waitlist Title"
        assert plan3.status == 'waitlist'

        # Test 5: Verify approval syncs from Planner
        print("\n--- Test 5: Approve Waitlist Sync ---")
        # Admin unassigns owner
        RoleService.assign_meeting_role(log3, None, is_admin=True)
        db.session.commit()
        
        # Approve waitlist
        print(f"DEBUG: Calling approve_waitlist for log3")
        success, msg = RoleService.approve_waitlist(log3)
        print(f"DEBUG: approve_waitlist success={success}, msg={msg}")
        assert success
        
        db.session.refresh(log3)
        assert log3.Project_ID == 1
        assert log3.Session_Title == "Waitlist Title"

        # Test 6: Verify cancellation clears details
        print("\n--- Test 6: Cancellation Cleanup ---")
        RoleService.cancel_meeting_role(log3, contact.id)
        db.session.commit()
        
        db.session.refresh(log3)
        print(f"After cancel - Project ID: {log3.Project_ID}")
        print(f"After cancel - Session Title: {log3.Session_Title}")
        assert log3.Project_ID is None
        assert log3.Session_Title is None

        print("\nALL TESTS PASSED!")
