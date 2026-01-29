import pytest
from app import db
from app.models.club import Club
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.models.meeting import Meeting
from app.models.session import SessionLog
from app.agenda_routes import _generate_logs_from_template
from datetime import date, time
import os
import csv

def test_meeting_creation_club_scoping(app):
    with app.app_context():
        # Consumes ID 1 (Global) so Club 1 and Club 2 are truly local
        dummy = Club(club_no="DUMMY", club_name="Global")
        db.session.add(dummy)
        db.session.commit()

        # 1. Setup two clubs with their own definitions
        club1 = Club(club_no="CLUB1", club_name="Club 1")
        club2 = Club(club_no="CLUB2", club_name="Club 2")
        db.session.add(club1)
        db.session.add(club2)
        db.session.flush()

        # Add a custom session type to Club 1
        st1 = SessionType(Title="Club1Only", club_id=club1.id)
        db.session.add(st1)
        
        # Add Generic types to both
        g1 = SessionType(Title="Generic", club_id=club1.id)
        g2 = SessionType(Title="Generic", club_id=club2.id)
        db.session.add(g1)
        db.session.add(g2)
        
        # Add a custom session type to Club 2
        st2 = SessionType(Title="Club2Only", club_id=club2.id)
        db.session.add(st2)
        
        db.session.commit()

        # 2. Create a meeting for Club 1
        meeting1 = Meeting(Meeting_Number=101, club_id=club1.id, status='unpublished', 
                          Meeting_Date=date(2026, 2, 1), Start_Time=time(19, 0))
        db.session.add(meeting1)
        db.session.commit()

        # 3. Create a dummy template CSV
        template_name = "test_template.csv"
        template_path = os.path.join(app.static_folder, 'mtg_templates', template_name)
        os.makedirs(os.path.dirname(template_path), exist_ok=True)
        
        with open(template_path, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Title', 'Role', 'Owner', 'Min', 'Max'])
            writer.writerow(['Club1Only', '', '', '', '5', '10'])

        # 4. Generate logs for Club 1 meeting using Club 1 context
        from flask import session
        with app.test_request_context():
            session['current_club_id'] = club1.id
            _generate_logs_from_template(meeting1, template_name)
            
            logs = SessionLog.query.filter_by(Meeting_Number=101).all()
            assert len(logs) == 1
            assert logs[0].Session_Title == "Club1Only"
            assert logs[0].Type_ID == st1.id

        # 5. Try generating for Club 2 meeting using Club 2 context but with Club1Only type in template
        meeting2 = Meeting(Meeting_Number=102, club_id=club2.id, status='unpublished',
                          Meeting_Date=date(2026, 2, 8), Start_Time=time(19, 0))
        db.session.add(meeting2)
        db.session.commit()
        
        with app.test_request_context():
            session['current_club_id'] = club2.id
            _generate_logs_from_template(meeting2, template_name)
            
            logs = SessionLog.query.filter_by(Meeting_Number=102).all()
            assert len(logs) == 1
            
            # Since Club2 doesn't have "Club1Only", it should fallback to 'Generic' or custom
            generic_id = SessionType.get_id_by_title('Generic', club2.id)
            assert logs[0].Type_ID == generic_id
            assert logs[0].Session_Title == "Club1Only"

        # Cleanup
        os.remove(template_path)
