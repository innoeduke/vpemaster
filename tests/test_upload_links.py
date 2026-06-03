import sys
import os
import unittest
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Club, Contact, UserClub, AuthRole, Permission, Meeting, UploadLink
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

class UploadLinksTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        db.session.configure(expire_on_commit=True)

        # Seed roles & permissions
        self.role_club_admin = AuthRole(name="ClubAdmin", level=4)
        self.role_member = AuthRole(name="Member", level=1)
        
        self.perm_upload_manage = Permission(name=Permissions.MEDIA_MANAGE, description="Manage Uploads")
        self.role_club_admin.permissions.append(self.perm_upload_manage)
        
        db.session.add_all([self.role_club_admin, self.role_member, self.perm_upload_manage])
        
        # Create Club
        self.club = Club(club_name="Upload Test Club", club_no="999999")
        db.session.add(self.club)
        db.session.commit()

        # Refresh instances
        db.session.refresh(self.club)
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def create_user(self, username, role_name):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()
        
        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()
        
        role = AuthRole.query.filter_by(name=role_name).first()
        uc = UserClub(user_id=u.id, club_id=self.club.id, contact_id=c.id, is_home=True, auth_role_id=role.id if role else None)
        db.session.add(uc)
        db.session.commit()
        
        db.session.refresh(u)
        db.session.refresh(c)
        return u, c

    def login(self, username):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data=dict(
            username=username,
            password='password',
            club_names=str(self.club.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id
            sess['current_club_id'] = self.club.id

    def test_model_expiration_and_properties(self):
        """Test UploadLink model properties and expiration validation."""
        link = UploadLink(
            code="testcode1",
            title="Photos Link",
            club_id=self.club.id,
            is_active=True
        )
        db.session.add(link)
        db.session.commit()
        
        # Test not expired without expires_at
        self.assertFalse(link.is_expired)
        
        # Test expired in past
        link.expires_at = datetime.now() - timedelta(hours=1)
        db.session.commit()
        self.assertTrue(link.is_expired)
        
        # Test not expired in future
        link.expires_at = datetime.now() + timedelta(hours=1)
        db.session.commit()
        self.assertFalse(link.is_expired)

    def test_link_to_existing_and_non_existing_meetings(self):
        """Test linking upload jobs to meetings and handling non-existent meeting numbers."""
        # Create meeting
        m = Meeting(Meeting_Number=42, status='not started', club_id=self.club.id)
        db.session.add(m)
        db.session.commit()
        
        admin_user, _ = self.create_user("admin", "ClubAdmin")
        self.login("admin")
        
        # Test 1: Create link with existing meeting number
        res = self.client.post('/uploads/create', data=dict(
            meeting_number="42"
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        link = UploadLink.query.filter_by(meeting_id=m.id).first()
        self.assertIsNotNone(link)
        self.assertEqual(link.title, "Meeting #42")
        self.assertIsNotNone(link.code)
        
        # Test 2: Create link with non-existent meeting number
        res = self.client.post('/uploads/create', data=dict(
            meeting_number="999"
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        link999 = UploadLink.query.filter_by(meeting_id=None).first()
        self.assertIsNotNone(link999)
        self.assertIsNone(link999.meeting_id) # Should default to None
        self.assertEqual(link999.title, "Unspecified")

    def test_routes_access_control(self):
        """Test access controls on uploads blueprint routes."""
        admin_user, _ = self.create_user("admin", "ClubAdmin")
        member_user, _ = self.create_user("member", "Member")
        
        # Create an upload link
        link = UploadLink(
            code="public1",
            title="Public Upload Folder",
            club_id=self.club.id,
            is_active=True
        )
        db.session.add(link)
        db.session.commit()
        
        # 1. Unauthenticated client tests
        # Can view public upload page
        res = self.client.get('/upload/public1')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Public Upload Folder", res.data)
        
        # Cannot view dashboard or view files
        res = self.client.get('/uploads/')
        self.assertEqual(res.status_code, 302) # Redirects to login
        res = self.client.get('/uploads/public1/files')
        self.assertEqual(res.status_code, 302)
        
        # 2. Authenticated Member tests (no FILE_UPLOAD_MANAGE permission)
        self.login("member")
        res = self.client.get('/uploads/')
        self.assertEqual(res.status_code, 403) # Forbidden
        res = self.client.get('/uploads/public1/files')
        self.assertEqual(res.status_code, 403)
        
        # 3. Authenticated Admin tests (has FILE_UPLOAD_MANAGE permission)
        self.login("admin")
        res = self.client.get('/uploads/')
        self.assertEqual(res.status_code, 200)
        res = self.client.get('/uploads/public1/files')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Public Upload Folder", res.data)

    def test_inactive_and_expired_public_upload_blocking(self):
        """Test that inactive or expired upload links block uploads and display messages."""
        # 1. Inactive link
        link_inactive = UploadLink(
            code="inactivecode",
            title="Inactive Upload",
            club_id=self.club.id,
            is_active=False
        )
        # 2. Expired link
        link_expired = UploadLink(
            code="expiredcode",
            title="Expired Upload",
            club_id=self.club.id,
            expires_at=datetime.now() - timedelta(days=1),
            is_active=True
        )
        db.session.add_all([link_inactive, link_expired])
        db.session.commit()
        
        # Inactive link page check
        res = self.client.get('/upload/inactivecode')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"This upload link has been disabled by the administrator.", res.data)
        
        # Inactive link upload POST check
        res = self.client.post('/upload/inactivecode', data=dict())
        self.assertEqual(res.status_code, 403)
        
        # Expired link page check
        res = self.client.get('/upload/expiredcode')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"This upload link has expired.", res.data)
        
        # Expired link upload POST check
        res = self.client.post('/upload/expiredcode', data=dict())
        self.assertEqual(res.status_code, 403)

    def test_upload_quota_enforcement(self):
        """Test that uploads are blocked when club storage exceeds the quota."""
        import io
        
        # Create active upload link
        link = UploadLink(
            code="quotacode",
            title="Quota Limit Upload",
            club_id=self.club.id,
            is_active=True
        )
        db.session.add(link)
        db.session.commit()

        # 1. Normal state: GET page works, returns 200
        res = self.client.get('/upload/quotacode')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"storage quota has been exceeded", res.data)

        # 2. Exceeded state: Set MAX_CLUB_STORAGE to 0
        self.app.config['MAX_CLUB_STORAGE'] = 0
        
        # GET page should now show the quota warning
        res = self.client.get('/upload/quotacode')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"storage quota has been exceeded", res.data)

        # POST file upload should be refused (400 Bad Request)
        res = self.client.post('/upload/quotacode', data={
            'files[]': (io.BytesIO(b"test data"), "test.txt")
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"Upload refused. Your club has exceeded its maximum storage limit", res.data)

if __name__ == '__main__':
    unittest.main()
