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

    def test_message_trash_and_empty_trash_flow(self):
        """Test moving messages to trash, permanently deleting individually, and emptying trash."""
        # 1. alice sends a message to bob
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_id': self.recv1.id,
            'subject': 'Hello Bob',
            'body': 'Hi bob, this is alice.',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        msg_id = Message.query.first().id
        
        # 2. bob logs in, checks inbox, and deletes the message (soft delete -> goes to Trash)
        self.login(self.recv1, self.club)
        
        # Verify it is in Bob's inbox
        inbox_res = self.client.get('/api/messages/inbox')
        self.assertEqual(len(inbox_res.get_json()['messages']), 1)
        
        # Soft delete from inbox
        del_res = self.client.post(f'/messages/{msg_id}/delete?context=inbox')
        self.assertEqual(del_res.status_code, 200)
        
        # Verify it is no longer in Bob's inbox
        inbox_res2 = self.client.get('/api/messages/inbox')
        self.assertEqual(len(inbox_res2.get_json()['messages']), 0)
        
        # Verify it IS in Bob's trash
        trash_res = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res.get_json()['messages']), 1)
        self.assertEqual(trash_res.get_json()['messages'][0]['type'], 'inbox')
        
        # 3. permanently delete the message from Bob's trash
        perm_del_res = self.client.post(f'/messages/{msg_id}/delete?context=trash')
        self.assertEqual(perm_del_res.status_code, 200)
        
        # Verify it is no longer in Bob's trash
        trash_res2 = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res2.get_json()['messages']), 0)
        
        # 4. alice soft deletes from Sent (goes to Alice's Trash)
        self.login(self.sender, self.club)
        sent_res = self.client.get('/api/messages/sent')
        self.assertEqual(len(sent_res.get_json()['messages']), 1)
        
        del_sent_res = self.client.post(f'/messages/{msg_id}/delete?context=sent')
        self.assertEqual(del_sent_res.status_code, 200)
        
        # Verify no longer in Sent
        sent_res2 = self.client.get('/api/messages/sent')
        self.assertEqual(len(sent_res2.get_json()['messages']), 0)
        
        # Verify in Alice's Trash
        alice_trash = self.client.get('/api/messages/trash')
        self.assertEqual(len(alice_trash.get_json()['messages']), 1)
        self.assertEqual(alice_trash.get_json()['messages'][0]['type'], 'sent')
        
        # 5. Alice empties her Trash
        empty_res = self.client.post('/messages/empty-trash')
        self.assertEqual(empty_res.status_code, 200)
        
        # Verify Alice's Trash is empty
        alice_trash2 = self.client.get('/api/messages/trash')
        self.assertEqual(len(alice_trash2.get_json()['messages']), 0)

    def test_message_restore_flow(self):
        """Test restoring messages from trash back to Inbox or Sent."""
        # 1. Alice sends a message to Bob
        self.login(self.sender, self.club)
        res = self.client.post('/messages/send', data=json.dumps({
            'recipient_id': self.recv1.id,
            'subject': 'Hello Bob',
            'body': 'Hi bob, this is alice.',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 200)
        msg_id = Message.query.first().id
        
        # 2. Bob soft deletes the message (Inbox -> Trash)
        self.login(self.recv1, self.club)
        del_res = self.client.post(f'/messages/{msg_id}/delete?context=inbox')
        self.assertEqual(del_res.status_code, 200)
        
        # Verify it is in Bob's trash
        trash_res = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res.get_json()['messages']), 1)
        
        # 3. Bob restores the message from Trash
        restore_res = self.client.post(f'/messages/{msg_id}/restore')
        self.assertEqual(restore_res.status_code, 200)
        
        # Verify it is no longer in Bob's trash
        trash_res2 = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res2.get_json()['messages']), 0)
        
        # Verify it is back in Bob's inbox
        inbox_res = self.client.get('/api/messages/inbox')
        self.assertEqual(len(inbox_res.get_json()['messages']), 1)
        
        # 4. Alice soft deletes the message (Sent -> Trash)
        self.login(self.sender, self.club)
        del_sent_res = self.client.post(f'/messages/{msg_id}/delete?context=sent')
        self.assertEqual(del_sent_res.status_code, 200)
        
        # Verify in Alice's Trash
        trash_res_alice = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res_alice.get_json()['messages']), 1)
        
        # 5. Alice restores the message from Trash
        restore_sent_res = self.client.post(f'/messages/{msg_id}/restore')
        self.assertEqual(restore_sent_res.status_code, 200)
        
        # Verify it is no longer in Alice's trash
        trash_res_alice2 = self.client.get('/api/messages/trash')
        self.assertEqual(len(trash_res_alice2.get_json()['messages']), 0)
        
        # Verify it is back in Alice's sent
        sent_res = self.client.get('/api/messages/sent')
        self.assertEqual(len(sent_res.get_json()['messages']), 1)

    def test_message_pagination(self):
        """Test pagination query parameters and metadata in the Inbox and Sent APIs."""
        # 1. Alice sends 15 messages to Bob
        self.login(self.sender, self.club)
        for i in range(15):
            res = self.client.post('/messages/send', data=json.dumps({
                'recipient_id': self.recv1.id,
                'subject': f'Subject {i}',
                'body': f'Body {i}',
            }), content_type='application/json')
            self.assertEqual(res.status_code, 200)
            
        # 2. Bob logs in, checks page 1 of Inbox
        self.login(self.recv1, self.club)
        inbox_p1 = self.client.get('/api/messages/inbox?page=1')
        self.assertEqual(inbox_p1.status_code, 200)
        data_p1 = inbox_p1.get_json()
        self.assertEqual(len(data_p1['messages']), 10)
        self.assertEqual(data_p1['total'], 15)
        self.assertEqual(data_p1['pages'], 2)
        self.assertEqual(data_p1['current_page'], 1)
        
        # 3. Bob checks page 2 of Inbox
        inbox_p2 = self.client.get('/api/messages/inbox?page=2')
        self.assertEqual(inbox_p2.status_code, 200)
        data_p2 = inbox_p2.get_json()
        self.assertEqual(len(data_p2['messages']), 5)
        self.assertEqual(data_p2['total'], 15)
        self.assertEqual(data_p2['pages'], 2)
        self.assertEqual(data_p2['current_page'], 2)

    def test_recipient_autocomplete_scoping_and_fallback(self):
        """Test autocomplete recipient logic context scoping and exact username fallback."""
        # 1. Create a second club and a user in it
        other_club = Club(club_name="Other Club", club_no="222222")
        db.session.add(other_club)
        db.session.commit()
        
        # User in the same club as alice (current club)
        # recv1 (bob), recv2 (carol), recv3 (dave) are already in self.club
        
        # Create an external user (eve) who is only in other_club
        external_user, _ = self._make_user("eve", other_club, self.role_member)
        
        # 2. Login as alice (sender)
        self.login(self.sender, self.club)
        
        # 3. Search with a query matching current club member (bob)
        # Should return bob
        res_bob = self.client.get('/api/messages/recipients?q=bo')
        self.assertEqual(res_bob.status_code, 200)
        data_bob = res_bob.get_json()
        self.assertTrue(any(u['name'] == 'bob' for u in data_bob))
        
        # 4. Search with a query matching external user (eve) but NOT exact username (e.g. substring 'ev')
        # Should NOT return eve
        res_eve_sub = self.client.get('/api/messages/recipients?q=ev')
        self.assertEqual(res_eve_sub.status_code, 200)
        data_eve_sub = res_eve_sub.get_json()
        self.assertFalse(any(u['name'] == 'eve' for u in data_eve_sub))
        
        # 5. Search with exact username for external user ('eve')
        # Should return eve
        res_eve_exact = self.client.get('/api/messages/recipients?q=eve')
        self.assertEqual(res_eve_exact.status_code, 200)
        data_eve_exact = res_eve_exact.get_json()
        self.assertTrue(any(u['name'] == 'eve' for u in data_eve_exact))
        
        # 6. Verify current user (alice) is never in the results
        res_self = self.client.get('/api/messages/recipients?q=alice')
        self.assertEqual(res_self.status_code, 200)
        data_self = res_self.get_json()
        self.assertFalse(any(u['name'] == 'alice' for u in data_self))


if __name__ == '__main__':


    unittest.main()
