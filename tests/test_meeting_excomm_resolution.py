import pytest
from datetime import date
from app.models import Meeting, ExComm, Club, Contact
from app import db

def test_meeting_get_excomm_priority(app, default_club):
    with app.app_context():
        # Setup: Create two ExComms
        excomm1 = ExComm(
            club_id=default_club.id,
            excomm_term="24H1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            excomm_name="Old Excomm"
        )
        excomm2 = ExComm(
            club_id=default_club.id,
            excomm_term="24H2",
            start_date=date(2024, 7, 1),
            end_date=date(2024, 12, 31),
            excomm_name="New Excomm"
        )
        db.session.add_all([excomm1, excomm2])
        db.session.flush()

        # 1. Test Priority 1: Linked excomm_id
        meeting1 = Meeting(
            Meeting_Number=100,
            club_id=default_club.id,
            Meeting_Date=date(2024, 8, 1), # Should fall in excomm2
            excomm_id=excomm1.id # But explicitly linked to excomm1
        )
        db.session.add(meeting1)
        db.session.flush()
        
        assert meeting1.get_excomm().id == excomm1.id

        # 2. Test Priority 2: Date-based resolution
        meeting2 = Meeting(
            Meeting_Number=101,
            club_id=default_club.id,
            Meeting_Date=date(2024, 2, 1) # Falls in excomm1
        )
        db.session.add(meeting2)
        db.session.flush()
        
        assert meeting2.get_excomm().id == excomm1.id

        meeting3 = Meeting(
            Meeting_Number=102,
            club_id=default_club.id,
            Meeting_Date=date(2024, 8, 1) # Falls in excomm2
        )
        db.session.add(meeting3)
        db.session.flush()
        
        assert meeting3.get_excomm().id == excomm2.id

        # 3. Test Priority 3: Fallback to most recent
        meeting4 = Meeting(
            Meeting_Number=103,
            club_id=default_club.id,
            Meeting_Date=date(2023, 1, 1) # No ExComm for this date
        )
        db.session.add(meeting4)
        db.session.flush()
        
        # Should return the most recent one (excomm2)
        assert meeting4.get_excomm().id == excomm2.id

        db.session.rollback()
