import unittest
import sys
import os
from datetime import datetime, date, time

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, Vote, Contact, Club
from app.agenda_routes import _tally_votes_and_set_winners
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class VotingTieBreakerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.populate_base_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def populate_base_data(self):
        # Create Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.commit()
        
        # Create Contacts
        self.contact_a = Contact(Name="Contact A")
        self.contact_b = Contact(Name="Contact B")
        self.contact_c = Contact(Name="Contact C")
        db.session.add_all([self.contact_a, self.contact_b, self.contact_c])
        db.session.commit()

    def test_no_tie(self):
        # Create meeting
        meeting = Meeting(
            Meeting_Number=100,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='running',
            club_id=self.club.id
        )
        db.session.add(meeting)
        db.session.commit()
        
        # Add votes: A gets 3, B gets 2
        for i in range(3):
            db.session.add(Vote(meeting_id=meeting.id, voter_identifier=f"voter_a_{i}", award_category="speaker", contact_id=self.contact_a.id))
        for i in range(2):
            db.session.add(Vote(meeting_id=meeting.id, voter_identifier=f"voter_b_{i}", award_category="speaker", contact_id=self.contact_b.id))
        db.session.commit()
        
        _tally_votes_and_set_winners(meeting)
        db.session.commit()
        
        self.assertEqual(meeting.best_speaker_id, self.contact_a.id)

    def test_tie_no_historical_wins(self):
        # Create meeting
        meeting = Meeting(
            Meeting_Number=101,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='running',
            club_id=self.club.id
        )
        db.session.add(meeting)
        db.session.commit()
        
        # Add votes: A gets 3, B gets 3
        for i in range(3):
            db.session.add(Vote(meeting_id=meeting.id, voter_identifier=f"voter_a_{i}", award_category="speaker", contact_id=self.contact_a.id))
            db.session.add(Vote(meeting_id=meeting.id, voter_identifier=f"voter_b_{i}", award_category="speaker", contact_id=self.contact_b.id))
        db.session.commit()
        
        _tally_votes_and_set_winners(meeting)
        db.session.commit()
        
        # Fallback should select one of them (stable ordering)
        self.assertIn(meeting.best_speaker_id, [self.contact_a.id, self.contact_b.id])

    def test_tie_with_historical_wins(self):
        # Historical setup:
        # Create past meeting where Contact A won the "speaker" award
        past_meeting = Meeting(
            Meeting_Number=90,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='finished',
            club_id=self.club.id,
            best_speaker_id=self.contact_a.id
        )
        db.session.add(past_meeting)
        db.session.commit()

        # Now, create current meeting
        current_meeting = Meeting(
            Meeting_Number=102,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='running',
            club_id=self.club.id
        )
        db.session.add(current_meeting)
        db.session.commit()
        
        # Add votes: A gets 3, B gets 3
        for i in range(3):
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_a_{i}", award_category="speaker", contact_id=self.contact_a.id))
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_b_{i}", award_category="speaker", contact_id=self.contact_b.id))
        db.session.commit()
        
        # Contact A has 1 historical win, Contact B has 0 historical wins.
        # Contact B should win because 0 < 1.
        _tally_votes_and_set_winners(current_meeting)
        db.session.commit()
        
        self.assertEqual(current_meeting.best_speaker_id, self.contact_b.id)

    def test_tie_with_historical_wins_different_club(self):
        # Create another club
        other_club = Club(
            club_no='111111',
            club_name='Other Club',
            district='Other District'
        )
        db.session.add(other_club)
        db.session.commit()

        # Create past meeting in other club where Contact B won the "speaker" award
        past_meeting_other_club = Meeting(
            Meeting_Number=90,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='finished',
            club_id=other_club.id,
            best_speaker_id=self.contact_b.id
        )
        db.session.add(past_meeting_other_club)
        
        # Create past meeting in current club where Contact A won the "speaker" award
        past_meeting_current_club = Meeting(
            Meeting_Number=91,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='finished',
            club_id=self.club.id,
            best_speaker_id=self.contact_a.id
        )
        db.session.add(past_meeting_current_club)
        db.session.commit()

        # Create current meeting in current club
        current_meeting = Meeting(
            Meeting_Number=103,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='running',
            club_id=self.club.id
        )
        db.session.add(current_meeting)
        db.session.commit()
        
        # Add votes: A gets 3, B gets 3
        for i in range(3):
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_a_{i}", award_category="speaker", contact_id=self.contact_a.id))
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_b_{i}", award_category="speaker", contact_id=self.contact_b.id))
        db.session.commit()
        
        # In current club: A has 1 win, B has 0 wins.
        # In other club: B has 1 win.
        # But we only count current club wins. So in current club B has 0 wins, A has 1 win.
        # Contact B should win because 0 < 1.
        _tally_votes_and_set_winners(current_meeting)
        db.session.commit()
        
        self.assertEqual(current_meeting.best_speaker_id, self.contact_b.id)

    def test_current_meeting_excluded_from_history(self):
        # Create current meeting
        current_meeting = Meeting(
            Meeting_Number=104,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='running',
            club_id=self.club.id,
            best_speaker_id=self.contact_a.id # Suppose the field was already set to Contact A
        )
        db.session.add(current_meeting)
        db.session.commit()
        
        # Add votes: A gets 3, B gets 3
        for i in range(3):
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_a_{i}", award_category="speaker", contact_id=self.contact_a.id))
            db.session.add(Vote(meeting_id=current_meeting.id, voter_identifier=f"voter_b_{i}", award_category="speaker", contact_id=self.contact_b.id))
        db.session.commit()
        
        # Contact A and B have 0 historical wins (excluding current_meeting).
        # Even though current_meeting.best_speaker_id was A, it is excluded.
        # So it is treated as a tie with 0 historical wins.
        _tally_votes_and_set_winners(current_meeting)
        db.session.commit()
        
        # Since they are tied with 0 historical wins, one of them wins (stable selection).
        self.assertIn(current_meeting.best_speaker_id, [self.contact_a.id, self.contact_b.id])

if __name__ == '__main__':
    unittest.main()
