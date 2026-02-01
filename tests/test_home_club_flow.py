
import pytest
from app.models import User, Club, Message, UserClub
from app.auth.permissions import Permissions

def test_home_club_flow(client, app, default_club, seeded_permissions):
    with app.app_context():
        from app import db
        # 0. Ensure AuthRole and Permissions are linked
        from app.models import AuthRole, Permission, RolePermission
        from app.auth.permissions import Permissions as P
        
        # Ensure ClubAdmin role exists
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not club_admin_role:
             club_admin_role = AuthRole(name='ClubAdmin', level=8)
             db.session.add(club_admin_role)
             db.session.commit()
             
        # Ensure Permission exists (seeded_permissions fixture guarantees it, but let's get it)
        perm = Permission.query.filter_by(name=P.SETTINGS_EDIT_ALL).first()
        if not perm:
            # Fallback if seed failed or fixture issue
            perm = Permission(name=P.SETTINGS_EDIT_ALL, category='Settings')
            db.session.add(perm)
            db.session.commit()
            
        # Ensure Link
        link = RolePermission.query.filter_by(role_id=club_admin_role.id, permission_id=perm.id).first()
        if not link:
            db.session.add(RolePermission(role_id=club_admin_role.id, permission_id=perm.id))
            db.session.commit()

        # Ensure User Role exists (for level 1)
        user_role = AuthRole.query.filter_by(name='User').first()
        if not user_role:
             user_role = AuthRole(name='User', level=1)
             db.session.add(user_role)
             db.session.commit()
             
        # Ensure User has basic permissions (like AGENDA_VIEW) to access dashboard
        perm_agenda = Permission.query.filter_by(name=P.AGENDA_VIEW).first()
        if not perm_agenda:
             perm_agenda = Permission(name=P.AGENDA_VIEW, category='Agenda')
             db.session.add(perm_agenda)
             db.session.commit()
             
        link_user = RolePermission.query.filter_by(role_id=user_role.id, permission_id=perm_agenda.id).first()
        if not link_user:
            db.session.add(RolePermission(role_id=user_role.id, permission_id=perm_agenda.id))
            db.session.commit()

        # 1. Setup: Create another club and users
        club1 = default_club
        club2 = Club(club_name="Target Club", club_no="999888")
        db.session.add(club2)
        db.session.commit()
        
        # Admin User (in Club 2, Target Club) with SETTINGS_EDIT_ALL permission
        admin_user = User(username="admin_home", email="admin_home@test.com")
        admin_user.set_password("password")
        db.session.add(admin_user)
        db.session.commit()
        
        # Link admin to Club 2
        admin_level = club_admin_role.level
        
        db.session.add(UserClub(user_id=admin_user.id, club_id=club2.id, club_role_level=admin_level, is_home=True))
        
        # Requestor User (Member of Club 1 (Home) and Club 2)
        user = User(username="user_home", email="user_home@test.com", first_name="User", last_name="Home")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        
        # Ensure level=1 (Member) to avoid 403
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, club_role_level=1, is_home=True))
        db.session.add(UserClub(user_id=user.id, club_id=club2.id, club_role_level=1, is_home=False))
        db.session.commit()
        
        admin_id = admin_user.id
        user_id = user.id
        club1_id = club1.id
        club2_id = club2.id
    # 2. Login as User and Request Home Club Change to Club 2
    with client:
        # Standard login redirects to dashboard. We just confirm redirect (302) which means success.
        # We don't follow to avoid testing Dashboard permissions which are out of scope.
        login_resp = client.post('/login', data={'username': 'user_home', 'password': 'password', 'club_names': club1_id})
        assert login_resp.status_code == 302, f"Login failed: {login_resp.status_code}"
        
        response = client.post(f'/clubs/{club2_id}/request_home', json={})
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert response.json['success'] is True
        
    # 3. Verify Message Sent to Admin of Club 2
    with app.app_context():
        msg = Message.query.filter_by(recipient_id=admin_id).order_by(Message.id.desc()).first()
        assert msg is not None
        assert "Request to set Home Club" in msg.subject
        assert f"[HOME_CLUB_REQUEST:{user_id}:{club2_id}]" in msg.body
        message_id = msg.id

    # 4. Login as Admin and Approve
    with client:
        client.get('/logout', follow_redirects=True)
        client.post('/login', data={'username': 'admin_home', 'password': 'password', 'club_names': club2_id})
        
        response = client.post('/clubs/respond_home_request', json={
            'message_id': message_id,
            'action': 'approve'
        })
        assert response.status_code == 200
        assert response.json['success'] is True
        
    # 5. Verify Database Changes (User Home is now Club 2)
    with app.app_context():
        uc1 = UserClub.query.filter_by(user_id=user_id, club_id=club1_id).first()
        uc2 = UserClub.query.filter_by(user_id=user_id, club_id=club2_id).first()
        
        assert uc1.is_home is False
        assert uc2.is_home is True
        
        # Verify Notification to User
        user_msg = Message.query.filter_by(recipient_id=user_id).order_by(Message.id.desc()).first()
        assert "approved" in user_msg.body.lower()
        
        # Verify Original Message Updated
        orig_msg = db.session.get(Message, message_id)
        assert "[Responded: APPROVED]" in orig_msg.body

    # 6. Security Test: Unauthorized Attempt
    # Create another user who is NOT admin of Club 2
    with app.app_context():
        hacker = User(username="hacker", email="hacker@test.com")
        hacker.set_password("password")
        db.session.add(hacker)
        db.session.commit()
        # Hacker joins Club 2 as member only
        db.session.add(UserClub(user_id=hacker.id, club_id=club2.id, club_role_level=1)) 
        db.session.commit()
        hacker_id = hacker.id
        
        # Reset message for test
        msg = db.session.get(Message, message_id)
        msg.body = f"[HOME_CLUB_REQUEST:{user_id}:{club2_id}]" # Reset body tag
        db.session.commit()

    with client:
        client.get('/logout', follow_redirects=True)
        login_resp = client.post('/login', data={'username': 'hacker', 'password': 'password'}, follow_redirects=True)
        assert login_resp.status_code == 200
        
        # Attempt to approve
        response = client.post('/clubs/respond_home_request', json={
            'message_id': message_id,
            'action': 'approve'
        })
        
        # Should be ignored (200 OK + success=False)
        assert response.status_code == 200
        assert response.json['success'] is False
        
    # Verify NO change happened
    with app.app_context():
        # Ensure message body wasn't changed
        msg = db.session.get(Message, message_id)
        assert "[Responded:" not in msg.body
