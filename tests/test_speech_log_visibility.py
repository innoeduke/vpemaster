import pytest
import random
from app.models import db, Club, Contact, User, Meeting, SessionLog, SessionType, MeetingRole
from app.speech_logs_routes import _fetch_logs_with_filters
from datetime import date, time
from unittest.mock import patch

class TestSpeechLogVisibility:
    
    @pytest.fixture
    def setup_data(self, app):
        ctx = app.app_context()
        ctx.push()
        # Use random numbers to avoid collision
        club_no_a = random.randint(10000, 99999)
        club_no_b = random.randint(10000, 99999)
        
        def get_or_create_club(name, no):
            club = Club.query.filter_by(club_no=no).first()
            if not club:
                club = Club(club_name=name, club_no=no)
                db.session.add(club)
                db.session.commit()
            return club

        club_a = get_or_create_club(f"Club A {club_no_a}", club_no_a)
        club_b = get_or_create_club(f"Club B {club_no_b}", club_no_b)
        
        # Create User (SysAdmin) and Contact
        first_name = f"TestUser{random.randint(1000,9999)}"
        contact = Contact(
            Name=f"{first_name} User",
            first_name=first_name, 
            last_name="User", 
            Email=f"{first_name}@example.com"
        )
        db.session.add(contact)
        db.session.commit()
        
        user = User(username=first_name, email=f"{first_name}@example.com", contact_id=contact.id)
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # Create Meetings
        mtg_no_a = random.randint(1000, 9999)
        mtg_no_b = random.randint(1000, 9999)
        
        meeting_a = Meeting(Meeting_Number=mtg_no_a, club_id=club_a.id, Meeting_Date=date(2025, 1, 1))
        meeting_b = Meeting(Meeting_Number=mtg_no_b, club_id=club_b.id, Meeting_Date=date(2025, 1, 2))
        db.session.add_all([meeting_a, meeting_b])
        db.session.commit()
        
        # Create SessionType and Role for Speech (reuse or create)
        role = MeetingRole.query.filter_by(name="Speaker").first()
        if not role:
            role = MeetingRole(name="Speaker", type="standard", needs_approval=False, is_distinct=True)
            db.session.add(role)
            db.session.commit()
        
        st = SessionType.query.filter_by(Title="Speech Test").first()
        if not st:
            st = SessionType(Title="Speech Test", role_id=role.id)
            db.session.add(st)
            db.session.commit()
        
        # Create SessionLogs (Speeches)
        log_a = SessionLog(
            Meeting_Number=meeting_a.Meeting_Number,
            Type_ID=st.id,
            Owner_ID=contact.id,
            Session_Title="Speech in Club A"
        )
        log_b = SessionLog(
            Meeting_Number=meeting_b.Meeting_Number,
            Type_ID=st.id,
            Owner_ID=contact.id,
            Session_Title="Speech in Club B"
        )
        db.session.add_all([log_a, log_b])
        db.session.commit()
        
        yield {
            'club_a': club_a, 
            'club_b': club_b, 
            'contact': contact,
            'log_a': log_a,
            'log_b': log_b,
            'mtg_a': meeting_a,
            'mtg_b': meeting_b
        }
        ctx.pop()

    def test_logs_filtered_by_club(self, app, setup_data):
        with app.app_context():
            filters = {
                'speaker_id': setup_data['contact'].id,
                'meeting_number': None,
                'role': None,
                'pathway': None, 
                'level': None,
                'status': None
            }
            
            # Case 1: Current Club is Club A
            with patch('app.speech_logs_routes.get_current_club_id', return_value=setup_data['club_a'].id, create=True):
                logs = _fetch_logs_with_filters(filters)
                
                # We expect ONLY log_a. 
                # Currently (before fix), it will return BOTH.
                # So we assert specific failure or just log it.
                # To be a strict test, we check explicitly for what we WANT (1 log).
                
                # Filter logs to only those created in this test (in case DB has other data)
                relevant_log_ids = [setup_data['log_a'].id, setup_data['log_b'].id]
                filtered_logs = [l for l in logs if l.id in relevant_log_ids]
                
                assert len(filtered_logs) == 1, f"Expected 1 log, got {len(filtered_logs)}"
                assert filtered_logs[0].Meeting_Number == setup_data['mtg_a'].Meeting_Number
                assert filtered_logs[0].Session_Title == "Speech in Club A"
            
            # Case 2: Current Club is Club B
            with patch('app.speech_logs_routes.get_current_club_id', return_value=setup_data['club_b'].id, create=True):
                logs = _fetch_logs_with_filters(filters)
                
                relevant_log_ids = [setup_data['log_a'].id, setup_data['log_b'].id]
                filtered_logs = [l for l in logs if l.id in relevant_log_ids]

                assert len(filtered_logs) == 1, f"Expected 1 log, got {len(filtered_logs)}"
                assert filtered_logs[0].Meeting_Number == setup_data['mtg_b'].Meeting_Number
                assert filtered_logs[0].Session_Title == "Speech in Club B"
