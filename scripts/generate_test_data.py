import sys
import os
import random
from datetime import datetime, timedelta

# Add parent directory to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, SessionLog, SessionType, Role, Waitlist, Vote, Roster, RosterRole, Contact, Media
from app.constants import SessionTypeID

app = create_app()

def generate_test_meeting():
    with app.app_context():
        print("Creating test data...")
        
        # 1. Create a Meeting
        # Find a free meeting number
        existing_numbers = [m.Meeting_Number for m in Meeting.query.all()]
        meeting_number = 999
        while meeting_number in existing_numbers:
            meeting_number -= 1
            
        print(f"Creating meeting #{meeting_number}")
        
        meeting = Meeting(
            Meeting_Number=meeting_number,
            Meeting_Date=datetime.today().date(),
            start_time=datetime.now().time(),
            status='finished' # Ready for deletion
        )
        db.session.add(meeting)
        db.session.flush()

        # 2. Add Session Logs
        # Get some session types
        st_speaker = SessionType.query.filter_by(Title='Prepared Speech').first()
        st_tt = SessionType.query.filter_by(Title='Table Topics').first()
        
        # Get a contact
        contact = Contact.query.first()
        if not contact:
            print("No contacts found. Please seed contacts first.")
            return

        log1 = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=1,
            Type_ID=st_speaker.id if st_speaker else 1,
            Owner_ID=contact.id,
            Session_Title="Test Speech to Delete"
        )
        db.session.add(log1)
        
        # 3. Add Media linked to Log
        media = Media(log_id=log1.id, url="http://example.com/delete_me")
        db.session.add(media)
        # Link media to meeting too (just to test that link breaking)
        meeting.media = media

        # 4. Add Waitlist
        waitlist = Waitlist(
            session_log_id=log1.id, # Temporarily use log1 ID before commit? No, need ID.
            contact_id=contact.id,
            timestamp=datetime.utcnow()
        )
        # We need log1.id, so flush
        db.session.flush()
        waitlist.session_log_id = log1.id
        db.session.add(waitlist)

        # 5. Add Roster
        roster = Roster(
            meeting_number=meeting_number,
            contact_id=contact.id,
            ticket="Member"
        )
        db.session.add(roster)
        db.session.flush()
        
        # 6. Add Roster Role
        role = Role.query.first()
        if role:
            rr = RosterRole(roster_id=roster.id, role_id=role.id)
            db.session.add(rr)

        # 7. Add Votes
        vote = Vote(
            meeting_number=meeting_number,
            voter_identifier="test_user",
            contact_id=contact.id,
            score=5
        )
        db.session.add(vote)

        db.session.commit()
        print(f"Test meeting #{meeting_number} created with logs, waitlist, roster, votes, and media.")
        print(f"Run deletion test on meeting #{meeting_number}")

if __name__ == "__main__":
    generate_test_meeting()
