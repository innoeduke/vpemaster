import unittest
import sys
import os

# Add project root to path ensuring 'app' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Roster, Contact, Ticket, Meeting, Club
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestRosterQuantity(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed club
        self.club = Club(id=1, club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()

        # Seed contact
        self.contact = Contact(Name="Test User", Type="Member")
        db.session.add(self.contact)
        db.session.flush()

        # Seed ticket with a non-zero price
        self.ticket = Ticket(name="Paid Ticket", type="Member", price=25.50, club_id=self.club.id)
        db.session.add(self.ticket)
        db.session.flush()

        # Seed meeting
        from datetime import date
        self.meeting = Meeting(Meeting_Number=123, Meeting_Date=date(2026, 1, 1), club_id=self.club.id)
        db.session.add(self.meeting)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_default_quantity(self):
        """Verify that a roster entry defaults to a quantity of 1 and computes price correctly."""
        entry = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.contact.id,
            ticket_id=self.ticket.id
        )
        db.session.add(entry)
        db.session.commit()

        self.assertEqual(entry.quantity, 1)
        # 25.50 * 1 = 25.50
        self.assertAlmostEqual(entry.amount, 25.50)

    def test_custom_quantity(self):
        """Verify that a roster entry with a custom quantity computes amount correctly."""
        entry = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.contact.id,
            ticket_id=self.ticket.id,
            quantity=3
        )
        db.session.add(entry)
        db.session.commit()

        self.assertEqual(entry.quantity, 3)
        # 25.50 * 3 = 76.50
        self.assertAlmostEqual(entry.amount, 76.50)

    def test_update_quantity_recomputes_amount(self):
        """Verify that updating the quantity correctly updates the total amount."""
        entry = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.contact.id,
            ticket_id=self.ticket.id,
            quantity=2
        )
        db.session.add(entry)
        db.session.commit()

        self.assertAlmostEqual(entry.amount, 51.00)

        # Update quantity
        entry.quantity = 4
        db.session.commit()

        # 25.50 * 4 = 102.00
        self.assertAlmostEqual(entry.amount, 102.00)

    def test_multiple_orders_allowed(self):
        """Verify that the database allows multiple roster entries for the same contact in a meeting."""
        entry1 = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.contact.id,
            ticket_id=self.ticket.id,
            quantity=2,
            order_number=1
        )
        entry2 = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.contact.id,
            ticket_id=self.ticket.id,
            quantity=1,
            order_number=2
        )
        db.session.add_all([entry1, entry2])
        db.session.commit()

        # Retrieve both entries
        entries = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.contact.id).all()
        self.assertEqual(len(entries), 2)
        self.assertAlmostEqual(entries[0].amount, 51.00)
        self.assertAlmostEqual(entries[1].amount, 25.50)

if __name__ == '__main__':
    unittest.main()
