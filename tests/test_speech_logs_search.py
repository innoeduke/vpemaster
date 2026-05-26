import pytest
from unittest.mock import patch
from datetime import date
from app.models import db, Contact, SessionLog, SessionType, Meeting, MeetingRole, OwnerMeetingRoles

def test_search_logs_matching_scenarios(app, default_club):
    """Test backend _search_logs helper matches keywords across different fields."""
    with app.app_context():
        # 1. Create a meeting
        meeting = Meeting(Meeting_Number=975, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()
        
        # 2. Create roles and session types
        role_speaker = MeetingRole(name="Prepared Speaker", type="standard", needs_approval=False, has_single_owner=True)
        role_evaluator = MeetingRole(name="Speech Evaluator", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add_all([role_speaker, role_evaluator])
        db.session.commit()
        
        st_speech = SessionType(Title="Prepared Speech", role_id=role_speaker.id, club_id=default_club.id)
        st_eval = SessionType(Title="Evaluation", role_id=role_evaluator.id, club_id=default_club.id)
        db.session.add_all([st_speech, st_eval])
        db.session.commit()
        
        # 3. Create contacts
        contact_samantha = Contact(Name="Samantha Adams", Type="Member", first_name="Samantha", last_name="Adams")
        contact_bob = Contact(Name="Bob Jones", Type="Member", first_name="Bob", last_name="Jones")
        db.session.add_all([contact_samantha, contact_bob])
        db.session.commit()
        
        # 4. Create session logs
        log_speech = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st_speech.id,
            Session_Title="The Power of AI",
            project_code="PM1.1",
            Status="Booked"
        )
        log_eval = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=2,
            Type_ID=st_eval.id,
            Session_Title="Evaluation of Bob",
            project_code="GENERIC",
            Status="Completed"
        )
        db.session.add_all([log_speech, log_eval])
        db.session.flush()
        
        # Link owners via OwnerMeetingRoles
        omr_speech = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role_speaker.id,
            contact_id=contact_samantha.id,
            session_log_id=log_speech.id
        )
        omr_eval = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role_evaluator.id,
            contact_id=contact_bob.id,
            session_log_id=log_eval.id
        )
        db.session.add_all([omr_speech, omr_eval])
        db.session.commit()
        
        # Import the search helper
        from app.speech_logs_routes import _search_logs, _attach_owners
        
        # Search by contact name (Samantha)
        results = _search_logs("Samantha", can_view_all=True, current_club_id=default_club.id)
        _attach_owners(results)
        assert len(results) == 1
        assert results[0].id == log_speech.id
        
        # Search by meeting number (975)
        results = _search_logs("975", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 2
        
        # Search by role name (Evaluator)
        results = _search_logs("Evaluator", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 1
        assert results[0].id == log_eval.id
        
        # Search by project code (PM1.1)
        results = _search_logs("PM1.1", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 1
        assert results[0].id == log_speech.id
        
        # Search by speech title (Power)
        results = _search_logs("Power", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 1
        assert results[0].id == log_speech.id
        
        # Search with multiple keywords (Samantha 975 Speaker)
        results = _search_logs("Samantha 975 Speaker", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 1
        assert results[0].id == log_speech.id
        
        # Search with mismatching multiple keywords (Samantha Jones)
        results = _search_logs("Samantha Jones", can_view_all=True, current_club_id=default_club.id)
        assert len(results) == 0

def test_speech_logs_view_transitions(client, app, default_club, staff_user):
    """Test transitions to member and search view modes, and admin deprecation redirect."""
    with app.app_context():
        # Clean up any potential database records or just check routing
        pass

    # Authenticate client as staff_user (who has SPEECH_LOGS_VIEW_ALL)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # 1. Access speech logs with view_mode=admin -> should render member_view (or member view_mode inside Python context)
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get('/speech_logs?view_mode=admin')
        assert resp.status_code == 200
        # Check that meeting_view was not rendered, but member_view was
        # Let's inspect the html text or verify it loaded member toolbar
        html_text = resp.data.decode('utf-8')
        assert "Member" in html_text
        assert "btn-meeting-view" not in html_text # meeting button hidden/removed
        assert "Project" in html_text

    # 2. Access speech logs with search query q=Samantha -> should render search_view
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get('/speech_logs?q=Samantha')
        assert resp.status_code == 200
        html_text = resp.data.decode('utf-8')
        assert "Search Results for" in html_text
        
    # 3. Access speech logs with search query q=Samantha but without view all permission -> should NOT render search_view
    with patch('app.speech_logs_routes.is_authorized', return_value=False):
        resp = client.get('/speech_logs?q=Samantha')
        assert resp.status_code == 200
        html_text = resp.data.decode('utf-8')
        assert "Search Results for" not in html_text
        assert "Member" in html_text
