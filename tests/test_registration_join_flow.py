import pytest
from app.models import User, Club, Message, UserClub
from app.auth.permissions import Permissions

def test_registration_and_join_flow(client, app, default_club, seeded_permissions):
    with app.app_context():
        from app import db
        from app.models import AuthRole, Permission, RolePermission
        from app.auth.permissions import Permissions as P
        
        # Ensure ClubAdmin and User roles exist
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not club_admin_role:
             club_admin_role = AuthRole(name='ClubAdmin', level=8)
             db.session.add(club_admin_role)
             
        user_role = AuthRole.query.filter_by(name='User').first()
        if not user_role:
             user_role = AuthRole(name='User', level=1)
             db.session.add(user_role)
        # Link SETTINGS_EDIT to ClubAdmin
        perm = Permission.query.filter_by(name=P.SETTINGS_EDIT).first()
        if not perm:
            perm = Permission(name=P.SETTINGS_EDIT, category='Settings')
            db.session.add(perm)
            db.session.commit()
            
        link = RolePermission.query.filter_by(role_id=club_admin_role.id, permission_id=perm.id).first()
        if not link:
            db.session.add(RolePermission(role_id=club_admin_role.id, permission_id=perm.id))
            
        db.session.commit()

        # Create a club and an admin user for that club
        club = Club(club_name="Shanghai Leadership Toastmasters Club", club_no="123456")
        db.session.add(club)
        db.session.commit()

        admin = User(username="club_admin", email="admin@test.com")
        admin.set_password("AdminPassword123")
        db.session.add(admin)
        db.session.commit()

        # Link admin to the club as ClubAdmin
        db.session.add(UserClub(user_id=admin.id, club_id=club.id, auth_role_id=club_admin_role.id, is_home=True))
        db.session.commit()

        club_id = club.id
        admin_id = admin.id

    # 1. Test User Registration
    with client:
        # GET registration page
        resp = client.get('/register')
        assert resp.status_code == 200

        # Check a free username
        check_resp = client.post('/register/check_username', json={'username': 'brand_new_user'})
        assert check_resp.status_code == 200
        assert check_resp.json['available'] is True

        # Check a taken username
        check_resp = client.post('/register/check_username', json={'username': 'club_admin'})
        assert check_resp.status_code == 200
        assert check_resp.json['available'] is False

        # Check a free email
        check_resp = client.post('/register/check_email', json={'email': 'brand_new_email@test.com'})
        assert check_resp.status_code == 200
        assert check_resp.json['available'] is True

        # Check a taken email
        check_resp = client.post('/register/check_email', json={'email': 'admin@test.com'})
        assert check_resp.status_code == 200
        assert check_resp.json['available'] is False

        # POST registration with weak password
        resp = client.post('/register', data={
            'username': 'new_user',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new_user@test.com',
            'password': '123',
            'confirm_password': '123'
        })
        assert b'Password must be at least' in resp.data

        # POST registration successfully
        resp = client.post('/register', data={
            'username': 'new_user',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new_user@test.com',
            'password': 'Password123',
            'confirm_password': 'Password123'
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Registration successful' in resp.data

        # Try to register with duplicate email (should fail)
        resp_dup = client.post('/register', data={
            'username': 'another_user',
            'first_name': 'Another',
            'last_name': 'User',
            'email': 'new_user@test.com',
            'password': 'Password123',
            'confirm_password': 'Password123'
        }, follow_redirects=True)
        assert b'Email address is already registered' in resp_dup.data

    with app.app_context():
        user = User.query.filter_by(username='new_user').first()
        assert user is not None
        assert user.email == 'new_user@test.com'
        assert user.first_name == 'New'
        assert user.last_name == 'User'
        assert len(user.club_memberships) == 0
        assert user.status == 'unverified'
        token = user.get_verification_token()
        new_user_id = user.id

    # 2. Test Login for user with 0 club memberships
    with client:
        # Login should fail and warn about verification
        login_resp = client.post('/login', data={'username': 'new_user', 'password': 'Password123'}, follow_redirects=True)
        assert b'Please verify your email address before logging in' in login_resp.data

        # Verify email using the token
        verify_resp = client.get(f'/verify_email/{token}', follow_redirects=True)
        assert verify_resp.status_code == 200
        assert b'Your email address has been verified' in verify_resp.data

        # Login should now succeed and redirect to main index
        login_resp = client.post('/login', data={'username': 'new_user', 'password': 'Password123'}, follow_redirects=False)
        assert login_resp.status_code == 302

        # 3. Test request to join a club
        # GET clubs page to make sure it loads (and check that pending_club_ids is empty)
        resp = client.get('/clubs')
        assert resp.status_code == 200
        assert b'Shanghai Leadership Toastmasters Club' in resp.data

        # POST request to join
        req_resp = client.post(f'/clubs/{club_id}/request_join', json={})
        if req_resp.status_code != 200:
             print("ERROR IN JOIN REQUEST:", req_resp.json)
        assert req_resp.status_code == 200
        assert req_resp.json['success'] is True

    # 4. Verify message sent to admin
    with app.app_context():
        msg = Message.query.filter_by(recipient_id=admin_id).first()
        assert msg is not None
        assert f"[JOIN_REQUEST:{new_user_id}:{club_id}]" in msg.body
        message_id = msg.id

    # 5. Admin logs in and approves request
    with client:
        client.get('/logout')
        admin_login = client.post('/login', data={'username': 'club_admin', 'password': 'AdminPassword123', 'club_names': club_id})
        assert admin_login.status_code == 302

        # Admin approves
        approve_resp = client.post('/clubs/respond_join_request', json={
            'message_id': message_id,
            'action': 'approve'
        })
        assert approve_resp.status_code == 200
        assert approve_resp.json['success'] is True

    # 6. Verify requester is now a member of the club
    with app.app_context():
        uc = UserClub.query.filter_by(user_id=new_user_id, club_id=club_id).first()
        assert uc is not None
        assert uc.auth_role.name == 'User'
        assert uc.contact_id is not None
        
        # Verify notification message to the requester
        notif = Message.query.filter_by(recipient_id=new_user_id).first()
        assert notif is not None
        assert "approved" in notif.body.lower()

        # Verify join request tag replaced in message body
        msg_after = db.session.get(Message, message_id)
        assert "[Responded: APPROVED]" in msg_after.body
        assert msg_after.read is True


def test_email_uniqueness_on_profile_update(client, app):
    with app.app_context():
        from app import db
        # Create user 1
        u1 = User(username="user_one", email="one@test.com")
        u1.set_password("Password123")
        # Create user 2
        u2 = User(username="user_two", email="two@test.com")
        u2.set_password("Password123")
        db.session.add_all([u1, u2])
        db.session.commit()

    with client:
        # Log in as user 1
        client.post('/login', data={'username': 'user_one', 'password': 'Password123'})
        
        # Try to change email to user 2's email (two@test.com)
        resp = client.post('/profile', data={
            'action': 'update_profile',
            'first_name': 'User',
            'last_name': 'One',
            'email': 'two@test.com'
        }, follow_redirects=True)
        
        assert b'Email address is already registered' in resp.data

        # Change email to a unique one (three@test.com) - should succeed
        resp = client.post('/profile', data={
            'action': 'update_profile',
            'first_name': 'User',
            'last_name': 'One',
            'email': 'three@test.com'
        }, follow_redirects=True)
        
        assert b'Profile updated successfully' in resp.data

    with app.app_context():
        u1_updated = User.query.filter_by(username="user_one").first()
        assert u1_updated.email == 'three@test.com'


def test_verify_email_when_already_logged_in(client, app):
    with app.app_context():
        from app import db
        # Create an unverified user
        unverified_bob = User(username="unverified_bob", email="bob@test.com", status="unverified")
        unverified_bob.set_password("Password123")
        # Create an active user to log in as first
        active_alice = User(username="active_alice", email="alice@test.com", status="active")
        active_alice.set_password("Password123")
        db.session.add_all([unverified_bob, active_alice])
        db.session.commit()
        
        token = unverified_bob.get_verification_token()

    with client:
        # Log in as Alice first
        login_resp = client.post('/login', data={'username': 'active_alice', 'password': 'Password123'})
        assert login_resp.status_code == 302
        
        # Click verification link for Bob while logged in as Alice
        resp = client.get(f'/verify_email/{token}', follow_redirects=True)
        assert resp.status_code == 200
        assert b'Your email address has been verified' in resp.data
        
        # Verify Bob is active in DB
        with app.app_context():
            bob = User.query.filter_by(username='unverified_bob').first()
            assert bob.status == 'active'
            
        # Try to access a page that requires login, or check if we are redirected to login
        # '/logout' should require login and redirect because we were logged out.
        logout_resp = client.get('/logout')
        assert logout_resp.status_code == 302

