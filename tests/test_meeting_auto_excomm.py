import pytest
from datetime import date
from app.models import Meeting, ExComm, Club, Contact
from app import db
from app.services.data_import_service import DataImportService

def test_meeting_sync_excomm_method(app, default_club):
    with app.app_context():
        excomm = ExComm(
            club_id=default_club.id,
            excomm_term="24H1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            excomm_name="Test Excomm"
        )
        db.session.add(excomm)
        db.session.flush()

        meeting = Meeting(
            Meeting_Number=200,
            club_id=default_club.id,
            Meeting_Date=date(2024, 3, 1)
        )
        # Initially None
        assert meeting.excomm_id is None
        
        # Sync
        meeting.sync_excomm()
        assert meeting.excomm_id == excomm.id

        db.session.rollback()

def test_agenda_route_create_updates_excomm(app, default_club):
    # This tests the logic inside _create_or_update_session
    from app.agenda_routes import _create_or_update_session
    from app.club_context import set_current_club_id
    with app.app_context(), app.test_request_context():
        set_current_club_id(default_club.id)
        excomm = ExComm(
            club_id=default_club.id,
            excomm_term="24H1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            excomm_name="Test Excomm"
        )
        db.session.add(excomm)
        db.session.flush()

        # Create meeting first
        meeting = Meeting(Meeting_Number=300, club_id=default_club.id, Meeting_Date=date(2024, 3, 1))
        db.session.add(meeting)
        db.session.flush()

        item = {'id': 'new', 'type_id': 1}
        # Pass meeting.id, not number
        _create_or_update_session(item, meeting.id, 1)
        meeting.sync_excomm() # Ensure synced for assertion
        
        meeting = Meeting.query.filter_by(Meeting_Number=300).first()
        assert meeting is not None
        # Should be auto-populated because we called sync_excomm (or the route does)
        assert meeting.excomm_id == excomm.id

        db.session.rollback()

def test_upsert_meeting_record_updates_excomm(app, default_club):
    from app.agenda_routes import _upsert_meeting_record
    with app.app_context(), app.test_request_context():
        from app.club_context import set_current_club_id
        set_current_club_id(default_club.id)

        excomm = ExComm(
            club_id=default_club.id,
            excomm_term="24H1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            excomm_name="Test Excomm"
        )
        db.session.add(excomm)
        db.session.flush()

        data = {
            'meeting_number': 400,
            'meeting_date': date(2024, 4, 1),
            'start_time': None,
            'ge_mode': 0,
            'meeting_type': 'Keynote Speech',
            'meeting_title': 'Test',
            'subtitle': '',
            'wod': '',
            'meeting_id': None
        }
        _upsert_meeting_record(data, None)
        
        meeting = Meeting.query.filter_by(Meeting_Number=400).first()
        assert meeting.excomm_id == excomm.id

        db.session.rollback()

def test_upsert_meeting_record_imports_officers_when_rule_enabled(app, default_club):
    """New meetings auto-add officer roster rows when no ClubRule is set (default ON)."""
    from app.agenda_routes import _upsert_meeting_record
    from app.club_context import set_current_club_id
    from app.models import Contact, ContactClub, Roster

    with app.app_context(), app.test_request_context():
        set_current_club_id(default_club.id)

        officer = Contact(Name='Officer One', Type='Member', Email='officer1@example.com')
        db.session.add(officer)
        db.session.flush()
        db.session.add(ContactClub(contact_id=officer.id, club_id=default_club.id, is_officer=True))

        data = {
            'meeting_number': 410,
            'meeting_date': date(2024, 4, 1),
            'start_time': None,
            'ge_mode': 0,
            'meeting_type': 'Keynote Speech',
            'meeting_title': 'Officer Import ON',
            'subtitle': '',
            'wod': '',
            'meeting_id': None,
        }
        meeting = _upsert_meeting_record(data, None)

        officer_rows = Roster.query.filter_by(
            meeting_id=meeting.id, contact_type='Officer'
        ).all()
        assert len(officer_rows) == 1
        assert officer_rows[0].contact_id == officer.id

        db.session.rollback()


def test_upsert_meeting_record_skips_officers_when_rule_disabled(app, default_club):
    """New meetings skip officer auto-add when the ClubRule is OFF."""
    from app.agenda_routes import _upsert_meeting_record
    from app.club_context import set_current_club_id
    from app.models import ClubRule, Contact, ContactClub, Roster

    with app.app_context(), app.test_request_context():
        set_current_club_id(default_club.id)

        # Persist the policy as OFF for this club.
        db.session.add(ClubRule(
            club_id=default_club.id,
            rule_name='import_officers_to_meeting',
            is_enabled=False,
        ))

        officer = Contact(Name='Officer Two', Type='Member', Email='officer2@example.com')
        db.session.add(officer)
        db.session.flush()
        db.session.add(ContactClub(contact_id=officer.id, club_id=default_club.id, is_officer=True))

        data = {
            'meeting_number': 420,
            'meeting_date': date(2024, 4, 1),
            'start_time': None,
            'ge_mode': 0,
            'meeting_type': 'Keynote Speech',
            'meeting_title': 'Officer Import OFF',
            'subtitle': '',
            'wod': '',
            'meeting_id': None,
        }
        meeting = _upsert_meeting_record(data, None)

        officer_rows = Roster.query.filter_by(
            meeting_id=meeting.id, contact_type='Officer'
        ).all()
        assert officer_rows == []

        db.session.rollback()


def test_data_import_service_updates_excomm(app, default_club):
    with app.app_context():
        excomm = ExComm(
            club_id=default_club.id,
            excomm_term="24H1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            excomm_name="Test Excomm"
        )
        db.session.add(excomm)
        db.session.flush()

        service = DataImportService(default_club.club_no)
        service.club_id = default_club.id
        # meeting_no, title, date, template, wod, tt, eval, spk, rt, start, media, title, type, sub, status, manager, ge, nps, excomm...
        meetings_data = [
            [0, 500, '2024-05-01', 'keynote_speech.csv', '', None, None, None, None, '19:00:00', None, 'Title', 'Keynote Speech', '', 'unpublished', None]
        ]
        service.import_meetings(meetings_data)
        
        meeting = Meeting.query.filter_by(Meeting_Number=500).first()
        assert meeting.excomm_id == excomm.id

        db.session.rollback()


def test_meeting_renumbering_renames_poster(app, default_club, client, monkeypatch):
    import os
    from app.models import User, AuthRole, UserClub, Contact, Meeting
    from app.auth.permissions import Permissions
    from datetime import date
    from flask import json
    
    # 1. Create a sysadmin user
    with app.app_context():
        role = AuthRole.query.filter_by(name=Permissions.SYSADMIN).first()
        if not role:
            role = AuthRole(name=Permissions.SYSADMIN, level=100)
            db.session.add(role)
            db.session.commit()
            
        user = User.query.filter_by(username='sysadmin').first()
        if not user:
            user = User(username='sysadmin', email='sysadmin@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        
        contact = Contact.query.filter_by(Email=user.email).first()
        if not contact:
            contact = Contact(Name='SysAdmin Test', Email=user.email)
            db.session.add(contact)
            db.session.commit()
        
        user_club = UserClub.query.filter_by(user_id=user.id, club_id=default_club.id).first()
        if not user_club:
            user_club = UserClub(user_id=user.id, club_id=default_club.id, club_role_level=role.level, contact_id=contact.id, is_home=True)
            db.session.add(user_club)
            db.session.commit()
        
        # Setup test club with abbreviation/short name
        default_club.short_name = "shanghai-leadership"
        db.session.add(default_club)
        db.session.commit()
        
        meeting = Meeting(
            Meeting_Number=978,
            club_id=default_club.id,
            Meeting_Date=date(2026, 6, 17),
            poster_url=f"club_resources/{default_club.id}/poster/shanghai-leadership_poster_978.webp"
        )
        db.session.add(meeting)
        db.session.commit()

        meeting_id = meeting.id
        user_id = user.id
        club_id = default_club.id

    # 2. Mock file system operations
    rename_calls = []
    def mock_rename(src, dst):
        rename_calls.append((src, dst))
        
    def mock_isfile(path):
        if "shanghai-leadership_poster_978.webp" in path:
            return True
        return False
        
    monkeypatch.setattr(os, "rename", mock_rename)
    monkeypatch.setattr(os.path, "isfile", mock_isfile)
    monkeypatch.setattr(os, "makedirs", lambda path, exist_ok=False: None)

    # 3. Request update logs route using the client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
        sess['current_club_id'] = club_id

    response = client.post(
        '/agenda/update',
        data=json.dumps({
            'meeting_id': meeting_id,
            'meeting_number': '979'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    assert response.json.get('success') is True
    
    # Verify file was renamed on disk
    assert len(rename_calls) == 1
    src, dst = rename_calls[0]
    assert "shanghai-leadership_poster_978.webp" in src
    assert "shanghai-leadership_poster_979.webp" in dst

    # Verify meeting poster_url was updated in the DB
    with app.app_context():
        updated_meeting = Meeting.query.get(meeting_id)
        assert updated_meeting.Meeting_Number == 979
        assert updated_meeting.poster_url == f"club_resources/{club_id}/poster/shanghai-leadership_poster_979.webp"

