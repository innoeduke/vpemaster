import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, SessionLog, SessionType, Role, Contact
from app.constants import SessionTypeID

app = create_app()

def generate_keynote_meeting():
    with app.app_context():
        print("Generating Keynote Speech Meeting...")

        # 1. Find or Create necessary SessionTypes
        # We need types for: Intro, Keynote (Speech), Q&A (Table Topics?), Closing
        # Adapting to what's likely in the DB or falling back
        
        st_speech = SessionType.query.filter_by(Title='Prepared Speech').first()
        st_tt = SessionType.query.filter_by(Title='Table Topics').first()
        
        # Fallback for generic items if specific types don't exist
        # Often 'Officer Report' or similar might be used for generic segments, 
        # or we might need to rely on existing IDs. 
        # For this script, we'll try to find 'Network Session' or similar, else default to Table Topics for non-speech items
        st_generic = SessionType.query.filter(SessionType.Title.ilike('%Network%')).first()
        if not st_generic:
             st_generic = st_tt # Fallback
             
        if not st_speech:
            print("Error: 'Prepared Speech' session type not found.")
            return

        # 2. Create Meeting
        # Find a free meeting number
        existing_numbers = [m.Meeting_Number for m in Meeting.query.all()]
        meeting_number = 888 # Start check from 888
        while meeting_number in existing_numbers:
            meeting_number -= 1
            
        print(f"Creating Meeting #{meeting_number}")
        
        meeting = Meeting(
            Meeting_Number=meeting_number,
            type='Keynote Speech',
            Meeting_Date=datetime.today().date(),
            Start_Time=(datetime.now() + timedelta(days=1)).time(), # Tomorrow
            status='unpublished',
            Meeting_Title=f"Keynote Special #{meeting_number}"
        )
        db.session.add(meeting)
        db.session.flush()

        # 3. Add Session Logs within the meeting
        
        # Get a random contact for owner if possible, else None
        contact = Contact.query.first()
        owner_id = contact.id if contact else None

        logs = []
        
        # Agenda Item 1: Introduction
        logs.append(SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=1,
            Type_ID=st_generic.id if st_generic else 1, 
            Session_Title="Introduction & Welcome",
            Duration_Min=5,
            Duration_Max=10
        ))

        # Agenda Item 2: Keynote Speech
        logs.append(SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=2,
            Type_ID=st_speech.id,
            Owner_ID=owner_id,
            Session_Title="The Future of AI",
            Duration_Min=45,
            Duration_Max=60,
            Notes="Keynote Speaker: " + (contact.Name if contact else "Guest")
        ))
        
        # Agenda Item 3: Q&A
        logs.append(SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=3,
            Type_ID=st_tt.id if st_tt else 1, # Using TT type for Q&A often works for 'impromptu' segments
            Session_Title="Q&A Session",
            Duration_Min=15,
            Duration_Max=20
        ))

        # Agenda Item 4: Closing
        logs.append(SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=4,
            Type_ID=st_generic.id if st_generic else 1,
            Session_Title="Closing Remarks",
            Duration_Min=5,
            Duration_Max=5
        ))

        for log in logs:
            db.session.add(log)

        db.session.commit()
        print(f"Successfully created Keynote Meeting #{meeting_number} with {len(logs)} agenda items.")

if __name__ == "__main__":
    generate_keynote_meeting()
