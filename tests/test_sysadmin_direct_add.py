
import pytest
from app.models import User, Club, Message, UserClub, AuthRole

def setup_roles(db):
    """Ensure basic roles exist in the test database."""
    roles = [
        ('SysAdmin', 1000),
        ('ClubAdmin', 2),
        ('User', 1)
    ]
    for name, level in roles:
        role = AuthRole.query.filter_by(name=name).first()
        if not role:
            db.session.add(AuthRole(name=name, level=level))
    db.session.commit()

def test_sysadmin_direct_add(client, app, default_club):
    with app.app_context():
        from app import db
        setup_roles(db)
        
        club1 = default_club
        
        # SysAdmin User
        sysadmin = User(username="sysadmin_test", email="sysadmin_test@test.com")
        sysadmin.set_password("password")
        db.session.add(sysadmin)
        
        # Target User (already in system)
        target_user = User(username="target_user", email="target_user@test.com", first_name="Target", last_name="User")
        target_user.set_password("password")
        db.session.add(target_user)
        db.session.commit()
        
        # Assign SysAdmin role to sysadmin_test
        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        db.session.add(UserClub(user_id=sysadmin.id, club_id=club1.id, club_role_level=sysadmin_role.level))
        db.session.commit()
        
        target_id = target_user.id
        club1_id = club1.id

    # 2. Login as SysAdmin
    with client:
        login_resp = client.post('/login', data={'username': 'sysadmin_test', 'password': 'password', 'club_id': club1_id}, follow_redirects=True)
        assert login_resp.status_code == 200
        
        # 3. Request Join (should be direct add)
        response = client.post('/user/request_join', json={
            'target_user_id': target_id,
            'club_id': club1_id
        })
        
        assert response.status_code == 200
        assert response.json['success'] is True
        assert response.json.get('direct_add') is True
        
        # 4. Verify User added to UserClub immediately
        with app.app_context():
            uc = UserClub.query.filter_by(user_id=target_id, club_id=club1_id).first()
            assert uc is not None
            # Default role 1
            assert (uc.club_role_level & 1) == 1
            
            # 5. Verify NO invitation message was sent
            msg = Message.query.filter_by(recipient_id=target_id).first()
            assert msg is None

def test_non_sysadmin_still_invites(client, app, default_club):
    with app.app_context():
        from app import db
        setup_roles(db)
        
        club1 = default_club
        
        # Regular ClubAdmin
        club_admin = User(username="club_admin_test", email="club_admin_test@test.com")
        club_admin.set_password("password")
        db.session.add(club_admin)
        
        # Target User
        target_user = User(username="target_user_2", email="target_user_2@test.com")
        target_user.set_password("password")
        db.session.add(target_user)
        db.session.commit()
        
        # Assign ClubAdmin role (bitmask 2)
        club_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        db.session.add(UserClub(user_id=club_admin.id, club_id=club1.id, club_role_level=club_role.level))
        db.session.commit()
        
        target_id = target_user.id
        club1_id = club1.id

    # 2. Login as ClubAdmin
    with client:
        client.post('/login', data={'username': 'club_admin_test', 'password': 'password', 'club_id': club1_id})
        
        # 3. Request Join (should be invitation)
        response = client.post('/user/request_join', json={
            'target_user_id': target_id,
            'club_id': club1_id
        })
        
        assert response.status_code == 200
        assert response.json['success'] is True
        assert 'direct_add' not in response.json
        
        # 4. Verify NOT added yet
        with app.app_context():
            uc = UserClub.query.filter_by(user_id=target_id, club_id=club1_id).first()
            assert uc is None
            
            # 5. Verify invitation message WAS sent
            msg = Message.query.filter_by(recipient_id=target_id).first()
            assert msg is not None
            assert f"[CLUB_ID:{club1_id}]" in msg.body
