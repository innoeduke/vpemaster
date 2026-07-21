import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import (
    Topic, TopicResponse, TopicResponseLike, TopicComment, TopicCollection, CollectionItem,
    User, Club, Contact, UserClub, AuthRole, Permission,
)
from app.auth.permissions import Permissions
from app.services.topics_service import TopicService, ResponseService, CommentService, CollectionService
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class TableTopicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Seed roles & permissions
        self.perm_view = Permission(name=Permissions.TOPICS_VIEW, description="View Topics", category="topics", resource="topics", action="view")
        self.perm_write = Permission(name=Permissions.TOPICS_WRITE, description="Write Topics", category="topics", resource="topics", action="write")
        self.perm_comment = Permission(name=Permissions.TOPICS_COMMENT, description="Comment Topics", category="topics", resource="topics", action="comment")
        self.perm_manage = Permission(name=Permissions.TOPICS_MANAGE, description="Manage Topics", category="topics", resource="topics", action="manage")
        
        db.session.add_all([self.perm_view, self.perm_write, self.perm_comment, self.perm_manage])
        
        self.role_admin = AuthRole(name="ClubAdmin", level=4)
        self.role_admin.permissions.extend([self.perm_view, self.perm_write, self.perm_comment, self.perm_manage])
        
        self.role_member = AuthRole(name="Member", level=1)
        self.role_member.permissions.extend([self.perm_view, self.perm_write, self.perm_comment])
        
        db.session.add_all([self.role_admin, self.role_member])
        db.session.commit()

        # Create two clubs
        self.club_a = Club(club_name="Club A", club_no="111111")
        self.club_b = Club(club_name="Club B", club_no="222222")
        db.session.add_all([self.club_a, self.club_b])
        db.session.commit()

        # Create test client
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def create_user(self, username, role_name, club):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()

        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()

        role = AuthRole.query.filter_by(name=role_name).first()
        uc = UserClub(
            user_id=u.id, club_id=club.id, contact_id=c.id, is_home=True,
            auth_role_id=role.id if role else None,
        )
        db.session.add(uc)
        db.session.commit()
        db.session.refresh(u)
        return u, c

    def login(self, username, club):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data=dict(
            username=username,
            password='password',
            club_names=str(club.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = club.id
            sess['current_club_id'] = club.id

    def test_topic_crud_and_publishing(self):
        """Test topic creation, status publishing, and deletion."""
        admin, _ = self.create_user("admin_user", "ClubAdmin", self.club_a)
        
        # Create Topic
        topic = TopicService.create_topic("Title test", "Body test prompt", admin.id)
        self.assertEqual(topic.status, 'draft')
        
        # Publish Topic
        TopicService.publish_topic(topic.id)
        self.assertEqual(topic.status, 'published')
        self.assertIsNotNone(topic.published_at)

        # Get Current Featured
        curr = Topic.get_current()
        self.assertEqual(curr.id, topic.id)
        
        # Delete Topic
        TopicService.delete_topic(topic.id)
        self.assertIsNone(db.session.get(Topic, topic.id))

    def test_topics_admin_permissions(self):
        """Verify that only sysadmin can access the Table Topics admin panel and endpoints."""
        # 1. Create a sysadmin user
        sysadmin = User(username='sysadmin', email='sysadmin@example.com', status='active')
        sysadmin.set_password('password')
        db.session.add(sysadmin)
        db.session.commit()

        # Create a regular ClubAdmin user
        club_admin, _ = self.create_user("club_admin", "ClubAdmin", self.club_a)

        # 2. Try to access topics admin panel as club_admin -> Expect 403
        self.client.post('/login', data=dict(
            username="club_admin",
            password="password",
            club_names=str(self.club_a.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club_a.id
            sess['current_club_id'] = self.club_a.id
        
        response = self.client.get('/topics/admin')
        self.assertEqual(response.status_code, 403)

        # Try to publish a topic as club_admin -> Expect 403
        topic = TopicService.create_topic("Test topic", "Body text", sysadmin.id)
        response = self.client.post(f'/topics/admin/{topic.id}/publish')
        self.assertEqual(response.status_code, 403)

        # 3. Try to access topics admin panel as sysadmin -> Expect 200
        self.client.get('/logout') # Log out first
        self.client.post('/login', data=dict(
            username="sysadmin",
            password="password",
            club_names=str(self.club_a.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club_a.id
            sess['current_club_id'] = self.club_a.id

        response = self.client.get('/topics/admin')
        self.assertEqual(response.status_code, 200)

        # Publish a topic as sysadmin -> Expect 302 redirect
        response = self.client.post(f'/topics/admin/{topic.id}/publish')
        self.assertEqual(response.status_code, 302)
        db.session.refresh(topic)
        self.assertEqual(topic.status, 'published')

    def test_response_scoping_and_visibility(self):
        """Test Private, Club, and Public visibility levels for essay responses."""
        # Setup three users:
        # User A1 (Club A, Author)
        # User A2 (Club A, Viewer)
        # User B (Club B, Viewer)
        a1, _ = self.create_user("user_a1", "Member", self.club_a)
        a2, _ = self.create_user("user_a2", "Member", self.club_a)
        b, _ = self.create_user("user_b", "Member", self.club_b)

        topic = TopicService.create_topic("Prompt", "Reflect on this", a1.id)
        TopicService.publish_topic(topic.id)

        # 1. Private Response
        resp_private = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title="Private Thoughts", body="Only for me", visibility="private"
        )
        
        # Test visibility gates helper
        from app.topics_routes import check_response_visible
        self.assertTrue(check_response_visible(resp_private, a1))   # Author can see
        self.assertFalse(check_response_visible(resp_private, a2))  # Same club member cannot see
        self.assertFalse(check_response_visible(resp_private, b))   # Other club member cannot see

        # 2. Club Response
        resp_club = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title="Club Thoughts", body="For my club mates", visibility="club"
        )
        self.assertTrue(check_response_visible(resp_club, a1))   # Author can see
        self.assertTrue(check_response_visible(resp_club, a2))   # Same club member can see
        self.assertFalse(check_response_visible(resp_club, b))   # Other club member cannot see

        # 3. Public Response
        resp_public = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title="Public Thoughts", body="For everyone", visibility="public"
        )
        self.assertTrue(check_response_visible(resp_public, a1))   # Author can see
        self.assertTrue(check_response_visible(resp_public, a2))   # Same club member can see
        self.assertTrue(check_response_visible(resp_public, b))    # Other club member can see

    def test_commenting_rules_and_nesting(self):
        """Test comments logic, edit, delete, and 1-level reply nesting limit."""
        a1, _ = self.create_user("user_a1", "Member", self.club_a)
        a2, _ = self.create_user("user_a2", "Member", self.club_a)
        
        topic = TopicService.create_topic("Prompt", "Reflect on this", a1.id)
        TopicService.publish_topic(topic.id)
        
        resp = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title="Title", body="Body content", visibility="public"
        )

        # Add top comment
        c1 = CommentService.add_comment(response_id=resp.id, author_id=a2.id, body="Great essay!")
        self.assertIsNone(c1.parent_id)
        
        # Add reply comment
        c2 = CommentService.add_comment(response_id=resp.id, author_id=a1.id, body="Thank you!", parent_id=c1.id)
        self.assertEqual(c2.parent_id, c1.id)

        # Attempt nested reply to reply (depth = 2) -> Should fail
        with self.assertRaises(ValueError):
            CommentService.add_comment(response_id=resp.id, author_id=a2.id, body="Deep comment", parent_id=c2.id)

        # Edit Comment
        CommentService.update_comment(comment_id=c1.id, author_id=a2.id, body="Edited comment")
        self.assertEqual(c1.body, "Edited comment")

        # Unauthorized Edit -> Should fail
        with self.assertRaises(PermissionError):
            CommentService.update_comment(comment_id=c1.id, author_id=a1.id, body="Hack attempt")

        # Delete Comment (Authorized for essay author, comment author, or admin)
        CommentService.delete_comment(comment_id=c2.id, user_id=a1.id) # Essay author deletes reply
        self.assertIsNone(db.session.get(TopicComment, c2.id))

    def test_collections_saving(self):
        """Test private folders creation and bookmark additions/removals."""
        a1, _ = self.create_user("user_a1", "Member", self.club_a)

        topic = TopicService.create_topic("Prompt", "Reflect on this", a1.id)
        TopicService.publish_topic(topic.id)

        # Create Collection
        col = CollectionService.create_collection(user_id=a1.id, name="My Favorites")
        self.assertEqual(col.name, "My Favorites")

        # Add topic to collection
        item = CollectionService.add_item_to_collection(collection_id=col.id, user_id=a1.id, topic_id=topic.id)
        self.assertEqual(item.topic_id, topic.id)
        self.assertIsNone(item.response_id)

        # Verify saved status checklist helper
        saved_status = CollectionService.get_user_collections_for_item(user_id=a1.id, topic_id=topic.id)
        self.assertIn(col.id, saved_status)

        # Remove item from collection
        CollectionService.remove_item_from_collection(collection_id=col.id, user_id=a1.id, topic_id=topic.id)
        saved_status = CollectionService.get_user_collections_for_item(user_id=a1.id, topic_id=topic.id)
        self.assertNotIn(col.id, saved_status)

    def test_like_toggle_service_and_visibility_gating(self):
        """Likes are idempotent, unique per (user, response), and respect
        the same visibility gate as reading the reflection."""
        a1, _ = self.create_user("user_a1", "Member", self.club_a)
        a2, _ = self.create_user("user_a2", "Member", self.club_a)
        b, _ = self.create_user("user_b", "Member", self.club_b)

        topic = TopicService.create_topic("Prompt", "Reflect on this", a1.id)
        TopicService.publish_topic(topic.id)

        # Public reflection — everyone can like
        resp_pub = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title=None, body="For everyone", visibility="public"
        )

        # Like -> toggle returns (True, 1)
        liked, count = ResponseService.toggle_like(resp_pub.id, a2.id)
        self.assertTrue(liked)
        self.assertEqual(count, 1)

        # Author may like their own reflection
        liked, count = ResponseService.toggle_like(resp_pub.id, a1.id)
        self.assertTrue(liked)
        self.assertEqual(count, 2)

        # Unliking returns (False, decremented)
        liked, count = ResponseService.toggle_like(resp_pub.id, a2.id)
        self.assertFalse(liked)
        self.assertEqual(count, 1)

        # Unique constraint — rapidly toggling must never create more
        # than one row per (response, user). At this point a1 is still
        # liked (from step 291) and a2 has unliked, so count == 1.
        ResponseService.toggle_like(resp_pub.id, a1.id)   # unlike -> 0
        ResponseService.toggle_like(resp_pub.id, a1.id)   # re-like -> 1
        ResponseService.toggle_like(resp_pub.id, a1.id)   # unlike -> 0
        self.assertEqual(
            TopicResponseLike.query.filter_by(response_id=resp_pub.id).count(),
            0
        )

        # Private reflection — visibility gate blocks liking as a non-author
        resp_priv = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title=None, body="Only me", visibility="private"
        )
        from app.topics_routes import check_response_visible
        self.assertFalse(check_response_visible(resp_priv, b))

        # Liking is gated on the route side; the service itself just
        # returns (liked, count) — visibility is the route's call.
        liked, count = ResponseService.toggle_like(resp_priv.id, a1.id)
        self.assertTrue(liked)

        # populate_likes batch-loads count + liked-by-me flag
        TopicResponse.populate_likes([resp_pub, resp_priv], user_id=a1.id)
        self.assertEqual(resp_pub._like_count, 0)
        self.assertFalse(resp_pub._liked_by_me)
        self.assertEqual(resp_priv._like_count, 1)
        self.assertTrue(resp_priv._liked_by_me)

    def test_like_route_ajax(self):
        """The /response/<id>/like endpoint toggles and returns the
        updated (liked, count) payload; visibility is enforced."""
        a1, _ = self.create_user("user_a1", "Member", self.club_a)
        b, _ = self.create_user("user_b", "Member", self.club_b)

        topic = TopicService.create_topic("Prompt", "Reflect on this", a1.id)
        TopicService.publish_topic(topic.id)

        # Public reflection visible to B
        resp = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title=None, body="Public essay", visibility="public"
        )

        self.login("user_b", self.club_b)

        # First call — like
        r = self.client.post(f'/response/{resp.id}/like')
        self.assertEqual(r.status_code, 200)
        payload = r.get_json()
        self.assertTrue(payload['success'])
        self.assertTrue(payload['liked'])
        self.assertEqual(payload['count'], 1)

        # Second call — unlike
        r = self.client.post(f'/response/{resp.id}/like')
        payload = r.get_json()
        self.assertTrue(payload['success'])
        self.assertFalse(payload['liked'])
        self.assertEqual(payload['count'], 0)

        # Private reflection not visible to B — endpoint returns 404
        priv = ResponseService.create_response(
            topic_id=topic.id, author_id=a1.id, club_id=self.club_a.id,
            title=None, body="Secret", visibility="private"
        )
        r = self.client.post(f'/response/{priv.id}/like')
        self.assertEqual(r.status_code, 404)


if __name__ == '__main__':
    unittest.main()
