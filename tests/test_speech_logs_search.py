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
        # The member view's filter form has a unique id
        html_text = resp.data.decode('utf-8')
        assert "speech-logs-filter-form" in html_text
        assert "btn-meeting-view" not in html_text # meeting button hidden/removed

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
        assert "speech-logs-filter-form" in html_text


def test_search_logs_returns_all_timer_logs_for_contact(app, default_club):
    """
    Regression test for: searching 'Timer' on Kyle Wei's journal page returned only
    1 row instead of all 5–6 Timer logs.

    Each Timer meeting creates two SessionLogs (Timer Introduction + Timer Report)
    for the same owner at the same meeting number. The search must NOT collapse
    these via dedup nor via the (owner, role) role-consolidation step.
    """
    with app.app_context():
        # Use club 2 (Shanghai Leadership Toastmasters) — matches Kyle's real data
        club = db.session.get(__import__('app.models', fromlist=['Club']).Club, 2) or default_club

        # Contact (Kyle-equivalent)
        kyle = Contact(Name="Kyle Wei", Type="Member", first_name="Kyle", last_name="Wei")
        db.session.add(kyle)
        db.session.commit()

        # Timer role (functional / shared)
        role_timer = MeetingRole(name="Timer", type="functional",
                                 needs_approval=False, has_single_owner=False)
        db.session.add(role_timer)
        db.session.commit()

        st_timer = SessionType(Title="Timer Session", role_id=role_timer.id, club_id=club.id)
        db.session.add(st_timer)
        db.session.commit()

        # Build meetings, each with TWO Timer SessionLogs (Intro + Report) for Kyle
        meeting_numbers = [951, 932, 924]
        log_ids_by_meeting = {}
        for idx, mnum in enumerate(meeting_numbers, start=1):
            meeting = Meeting(Meeting_Number=mnum, Meeting_Date=date.today(),
                              club_id=club.id, status='finished')
            db.session.add(meeting)
            db.session.commit()

            log_intro = SessionLog(
                meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st_timer.id,
                Session_Title="Timer Introduction", Status="Completed", state="active",
            )
            log_report = SessionLog(
                meeting_id=meeting.id, Meeting_Seq=2, Type_ID=st_timer.id,
                Session_Title="Timer Report", Status="Completed", state="active",
            )
            db.session.add_all([log_intro, log_report])
            db.session.flush()

            # Shared-role OMR row (session_log_id IS NULL — matches legacy data)
            db.session.add(OwnerMeetingRoles(
                meeting_id=meeting.id, role_id=role_timer.id,
                contact_id=kyle.id, session_log_id=None,
            ))
            # Single-owner-style OMR row (session_log_id set — matches newer data)
            db.session.add(OwnerMeetingRoles(
                meeting_id=meeting.id, role_id=role_timer.id,
                contact_id=kyle.id, session_log_id=log_report.id,
            ))
            log_ids_by_meeting[meeting.id] = (log_intro.id, log_report.id)

        db.session.commit()

        from app.speech_logs_routes import _search_logs
        results = _search_logs('Timer', can_view_all=True, current_club_id=club.id,
                               contact_id=kyle.id)

        # 3 meetings × 2 logs = 6 distinct SessionLog rows. Must not be deduped.
        assert len(results) == 6, f"Expected 6 distinct Timer logs, got {len(results)}"

        # And every log id we created must appear exactly once.
        expected_ids = {lid for pair in log_ids_by_meeting.values() for lid in pair}
        returned_ids = {log.id for log in results}
        assert returned_ids == expected_ids


def test_search_route_renders_one_row_per_timer_log(client, app, default_club, staff_user):
    """
    Regression test for the visible bug: searching 'Timer' on Kyle's journal
    rendered only 1 (mostly empty) row. With the fix, the search-results table
    must render one row per matching SessionLog.
    """
    with app.app_context():
        kyle = Contact(Name="Kyle Search", Type="Member",
                       first_name="Kyle", last_name="Search")
        db.session.add(kyle)
        db.session.commit()

        role_timer = MeetingRole(name="Timer", type="functional",
                                 needs_approval=False, has_single_owner=False)
        db.session.add(role_timer)
        db.session.commit()

        st_timer = SessionType(Title="Timer Session", role_id=role_timer.id, club_id=default_club.id)
        db.session.add(st_timer)
        db.session.commit()

        meeting = Meeting(Meeting_Number=999, Meeting_Date=date.today(),
                          club_id=default_club.id, status='finished')
        db.session.add(meeting)
        db.session.commit()

        log_intro = SessionLog(meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st_timer.id,
                               Session_Title="Timer Introduction", Status="Completed", state="active")
        log_report = SessionLog(meeting_id=meeting.id, Meeting_Seq=2, Type_ID=st_timer.id,
                                Session_Title="Timer Report", Status="Completed", state="active")
        db.session.add_all([log_intro, log_report])
        db.session.flush()

        db.session.add(OwnerMeetingRoles(meeting_id=meeting.id, role_id=role_timer.id,
                                          contact_id=kyle.id, session_log_id=None))
        db.session.add(OwnerMeetingRoles(meeting_id=meeting.id, role_id=role_timer.id,
                                          contact_id=kyle.id, session_log_id=log_report.id))
        db.session.commit()

    # Log in as staff_user (already has SPEECH_LOGS_MANAGE via fixture) and patch
    # is_authorized so we can view Kyle's logs.
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get(f'/speech_logs?view_mode=search&speaker_id={kyle.id}&q=Timer')

    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    import re
    rows = re.findall(r'<tr style="border-bottom: 1px solid #e2e8f0;', html)
    # Two Timer logs at the same meeting — both must render as separate rows.
    assert len(rows) == 2, f"Expected 2 search result rows, got {len(rows)}"
    # And the speech titles must be distinct (proves we are not collapsing into one)
    assert "Timer Introduction" in html
    assert "Timer Report" in html


def test_attach_owners_dedupes_shared_role_owners(app, default_club):
    """
    Regression test for the visible bug: Kyle's Member column showed
    'Kyle Wei, Kyle Wei' for meetings where Kyle has TWO OwnerMeetingRoles rows
    for the same shared Timer role (one with session_log_id set, one with
    session_log_id IS NULL). _attach_owners() must dedupe so each contact
    appears once per log.
    """
    with app.app_context():
        kyle = Contact(Name="Kyle Owner Dedup", Type="Member",
                       first_name="Kyle", last_name="Owner Dedup")
        db.session.add(kyle)
        db.session.commit()

        role_timer = MeetingRole(name="Timer", type="functional",
                                 needs_approval=False, has_single_owner=False)
        db.session.add(role_timer)
        db.session.commit()

        st_timer = SessionType(Title="Timer Session", role_id=role_timer.id, club_id=default_club.id)
        db.session.add(st_timer)
        db.session.commit()

        meeting = Meeting(Meeting_Number=1234, Meeting_Date=date.today(),
                          club_id=default_club.id, status='finished')
        db.session.add(meeting)
        db.session.commit()

        log = SessionLog(meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st_timer.id,
                         Session_Title="Timer Report", Status="Completed", state="active")
        db.session.add(log)
        db.session.flush()

        # Two OMR rows for the same contact: one with session_log_id set,
        # one with session_log_id IS NULL (legacy/shared). _attach_owners must
        # dedupe so kyle appears once.
        db.session.add(OwnerMeetingRoles(meeting_id=meeting.id, role_id=role_timer.id,
                                          contact_id=kyle.id, session_log_id=log.id))
        db.session.add(OwnerMeetingRoles(meeting_id=meeting.id, role_id=role_timer.id,
                                          contact_id=kyle.id, session_log_id=None))
        db.session.commit()

        from app.speech_logs_routes import _attach_owners
        _attach_owners([log])

        assert len(log._cached_owners) == 1, (
            f"Expected Kyle to appear once, got {len(log._cached_owners)} owners"
        )
        assert log._cached_owners[0].id == kyle.id
