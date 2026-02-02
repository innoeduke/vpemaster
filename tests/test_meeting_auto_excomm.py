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

        item = {'id': 'new', 'type_id': 1}
        # Mocking or ensuring session type 1 exists might be needed if it fails
        # But here we focus on meeting creation
        _create_or_update_session(item, 300, 1)
        
        meeting = Meeting.query.filter_by(Meeting_Number=300).first()
        assert meeting is not None
        # Should be auto-populated because _create_or_update_session calls it
        # Note: _create_or_update_session doesn't have a club_id context directly, 
        # it uses current_club_id which might be tricky in pure unit test without session.
        # However, Meeting.get_excomm() uses its own club_id.
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
            'wod': ''
        }
        _upsert_meeting_record(data, None)
        
        meeting = Meeting.query.filter_by(Meeting_Number=400).first()
        assert meeting.excomm_id == excomm.id

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
            [0, 500, '2024-05-01', 'default.csv', '', None, None, None, None, '19:00:00', None, 'Title', 'Keynote Speech', '', 'unpublished', None]
        ]
        service.import_meetings(meetings_data)
        
        meeting = Meeting.query.filter_by(Meeting_Number=500).first()
        assert meeting.excomm_id == excomm.id

        db.session.rollback()
