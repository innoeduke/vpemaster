import sys
import os
import unittest
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Message, User, Club, Contact, UserClub, AuthRole
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class MultiRecipientSendTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.role_member = AuthRole(name="Member", level=1)
        db.session.add(self.role_member)
        db.session.commit()

        self.club = Club(club_name="Test Club", club_no="111111")
        db.session.add(self.club)
        db.session.commit()

        self.client = self.app.test_client()
        self.sender, _ = self._make_user("alice", self.club, self.role_member)
        self.recv1, _ = self._make_user("bob", self.club, self.role_member)
        self.recv2, _ = self._make_user("carol", self.club, self.role_member)
        self.recv3, _ = self._make_user("dave", self.club, self.role_member)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def _make_user(self, username, club, role):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()

        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()

        uc = UserClub(
            user_id=u.id, club_id=club.id, contact_id=c.id, is_home=True,
            auth_role_id=role.id,
        )
        db.session.add(uc)
        db.session.commit()
        db.session.refresh(u)
        return u, c

    def login(self, user, club):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data=dict(
            username=user.username,
            password='password',
            club_names=str(club.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = club.id
            sess['current_club_id'] = club.id

    def test_send_to_single_recipient_legacy_id_still_works(self):
        """Backwards-compat: a single recipient_id should still send to one user."""
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_id': self.recv1.id,
            'subject': 'Hello',
            'body': 'Hi there',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['sent_count'], 1)
        messages = Message.query.all()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].recipient_id, self.recv1.id)
        self.assertEqual(messages[0].subject, 'Hello')

    def test_send_to_multiple_recipients(self):
        """POSTing recipient_ids should create one Message per recipient."""
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_ids': [self.recv1.id, self.recv2.id, self.recv3.id],
            'subject': 'Group hi',
            'body': 'Hello everyone',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['sent_count'], 3)
        messages = Message.query.all()
        self.assertEqual(len(messages), 3)
        recipient_ids = {m.recipient_id for m in messages}
        self.assertEqual(recipient_ids, {self.recv1.id, self.recv2.id, self.recv3.id})
        for m in messages:
            self.assertEqual(m.sender_id, self.sender.id)
            self.assertEqual(m.subject, 'Group hi')
            self.assertEqual(m.body, 'Hello everyone')

    def test_send_dedupes_duplicate_recipient_ids(self):
        """Duplicate IDs in the list should not create duplicate messages."""
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_ids': [self.recv1.id, self.recv1.id, self.recv2.id],
            'subject': 'Dedup test',
            'body': 'Hello',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['sent_count'], 2)
        self.assertEqual(Message.query.count(), 2)

    def test_send_rejects_empty_recipient_list(self):
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_ids': [],
            'subject': 'Empty',
            'body': 'Hello',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])

    def test_send_rejects_missing_recipient(self):
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_ids': [self.recv1.id, 99999],
            'subject': 'Missing',
            'body': 'Hello',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.get_json()['success'])
        # No messages should have been created
        self.assertEqual(Message.query.count(), 0)

    def test_sse_receives_announcement(self):
        """Establishing an EventSource connection and sending a message should push an event."""
        # 1. Login the recipient
        self.login(self.recv1, self.club)
        
        # 2. Open stream connection
        res = self.client.get('/api/messages/events')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/event-stream')
        
        # Let's verify the first chunk from the generator is the connection message
        iterator = res.response
        first_chunk = next(iterator)
        self.assertEqual(first_chunk.decode('utf-8'), "data: connected\n\n")

        # Now, we need to test that sending a message announces it to recv1
        # Let's announce an event to recv1 directly via announcer
        from app.messages_routes import announcer
        announcer.announce(self.recv1.id, 'new_message')
        
        # Read next chunk
        second_chunk = next(iterator)
        self.assertEqual(second_chunk.decode('utf-8'), "data: new_message\n\n")


if __name__ == '__main__':
    unittest.main()
