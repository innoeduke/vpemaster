import os
import sys
import pytest
from datetime import date, time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Club, SessionType, Meeting, SessionLog, MeetingRole
from app.agenda_routes import _generate_logs_from_template
from app.club_context import set_current_club_id
from app.constants import GLOBAL_CLUB_ID

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    SECRET_KEY = 'test_key'

def test_reproduce_session_type_lookup():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Setup: Ensure Global Club 1 exists
        global_club = db.session.get(Club, GLOBAL_CLUB_ID)
        if not global_club:
            global_club = Club(id=GLOBAL_CLUB_ID, club_no="0", club_name="Global Club")
            db.session.add(global_club)
        
        # Create a Global Role and Session Type
        global_role_name = "GlobalRole"
        global_role = MeetingRole.query.filter_by(name=global_role_name, club_id=GLOBAL_CLUB_ID).first()
        if not global_role:
            global_role = MeetingRole(name=global_role_name, type="standard", club_id=GLOBAL_CLUB_ID, needs_approval=False, has_single_owner=True)
            db.session.add(global_role)
            db.session.flush()

        global_type_title = "Global Standard Type"
        global_type = SessionType.query.filter_by(Title=global_type_title, club_id=GLOBAL_CLUB_ID).first()
        if not global_type:
            global_type = SessionType(Title=global_type_title, role_id=global_role.id, club_id=GLOBAL_CLUB_ID, Duration_Min=5, Duration_Max=7)
            db.session.add(global_type)
        
        # Ensure 'Generic' exists globally for fallback
        generic_type = SessionType.query.filter_by(Title="Generic", club_id=GLOBAL_CLUB_ID).first()
        if not generic_type:
             # Just reusing global role for simplicity, or create dummy
             generic_type = SessionType(Title="Generic", role_id=global_role.id, club_id=GLOBAL_CLUB_ID)
             db.session.add(generic_type)

        # Create a Local Club
        local_club = Club(club_no="99999", club_name="Local Club")
        db.session.add(local_club)
        db.session.commit()
        
        # Verify SessionType does NOT exist in Local Club
        local_check = SessionType.query.filter_by(Title=global_type_title, club_id=local_club.id).first()
        assert local_check is None, "Global Type should not exist in Local Club db"

        # Set Context
        with app.test_request_context():
            set_current_club_id(local_club.id)

        # Create a Meeting
        meeting = Meeting(
            Meeting_Number=101, 
            Meeting_Date=date.today(), 
            Start_Time=time(19, 0),
            club_id=local_club.id,
            status='unpublished'
        )
        db.session.add(meeting)
        db.session.commit()

        # Create a temporary template file
        template_content = f"{global_type_title},{global_type_title},,,5,7\n"
        template_filename = "temp_reproduce_template.csv"
        template_path = os.path.join(app.static_folder, 'mtg_templates', template_filename)
        
        if not os.path.exists(os.path.dirname(template_path)):
            os.makedirs(os.path.dirname(template_path))
            
        with open(template_path, 'w') as f:
            f.write("Type,Title,Role,Owner,Min,Max\n") # Header
            f.write(template_content)

        try:
            # Run the generation logic
            _generate_logs_from_template(meeting, template_filename)
            db.session.commit()

            # Verify the resulting log
            log = SessionLog.query.filter_by(Meeting_Number=meeting.Meeting_Number).first()
            assert log is not None
            
            print(f"Log SessionType ID: {log.Type_ID}")
            print(f"Global SessionType ID: {global_type.id}")
            print(f"Generic SessionType ID: {generic_type.id}")
            
            # THE ASSERTION: It should match global_type.id
            if log.Type_ID != global_type.id:
                print("FAILURE: Log matched to Generic/Wrong ID instead of Global ID")
                # We expect this to fail initially
                assert log.Type_ID == global_type.id, f"Expected {global_type.id} but got {log.Type_ID}"
            else:
                print("SUCCESS: Log correctly matched to Global ID")

        finally:
            # Cleanup
            if os.path.exists(template_path):
                os.remove(template_path)
            
            # Cleanup DB rows if needed (though test db usually tears down)
            pass

if __name__ == "__main__":
    test_reproduce_session_type_lookup()
