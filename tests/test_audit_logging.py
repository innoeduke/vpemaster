import pytest
from app.models import User, Club, UserClub, PermissionAudit

def test_login_and_enter_club_audit_logging(client, app, default_club):
    with app.app_context():
        from app import db
        # Create a test user
        user = User(username='audit_user', email='audit_user@example.com', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # Mark default_club as the home club
        uc = UserClub(user_id=user.id, club_id=default_club.id, is_home=True)
        db.session.add(uc)
        db.session.commit()

        user_id = user.id
        club_id = default_club.id
        club_name = default_club.club_name
        username = user.username

    # Count initial audit logs
    with app.app_context():
        initial_log_count = PermissionAudit.query.count()

    # 1. Test Login Audit Log
    response = client.post('/login', data={
        'username': 'audit_user',
        'password': 'password'
    })
    assert response.status_code == 302

    # Verify LOGIN audit log was created
    with app.app_context():
        logs = PermissionAudit.query.order_by(PermissionAudit.timestamp.desc()).all()
        assert len(logs) > initial_log_count
        
        login_log = next((l for l in logs if l.action == 'LOGIN'), None)
        assert login_log is not None
        assert login_log.admin_id == user_id
        assert login_log.target_type == 'USER'
        assert login_log.target_id == user_id
        assert login_log.target_name == username
        assert login_log.changes == 'User logged in'

    # 2. Test Enter Club Audit Log
    response = client.post(f'/clubs/{club_id}/enter')
    assert response.status_code == 200

    # Verify ENTER_CLUB audit log was created
    with app.app_context():
        logs = PermissionAudit.query.order_by(PermissionAudit.timestamp.desc()).all()
        
        enter_log = next((l for l in logs if l.action == 'ENTER_CLUB'), None)
        assert enter_log is not None
        assert enter_log.admin_id == user_id
        assert enter_log.target_type == 'CLUB'
        assert enter_log.target_id == club_id
        assert enter_log.target_name == club_name
        assert enter_log.changes == f"User entered club: {club_name}"


def test_audit_log_endpoint_restrictions(client, app, default_club):
    with app.app_context():
        from app import db
        # 1. Create a super club (ID=1) if it doesn't exist
        super_club = Club.query.get(1)
        if not super_club:
            super_club = Club(id=1, club_name="Super Club", club_no="000001")
            db.session.add(super_club)
        
        # Create a separate normal club (ID=2)
        normal_club = Club.query.get(2)
        if not normal_club:
            normal_club = Club(id=2, club_name="Normal Club", club_no="000002")
            db.session.add(normal_club)

        # 2. Create a sysadmin user
        sysadmin = User(username='sysadmin', email='sysadmin@example.com', status='active')
        sysadmin.set_password('password')
        db.session.add(sysadmin)
        db.session.flush()

        # Link sysadmin to super club
        uc_sys = UserClub(user_id=sysadmin.id, club_id=1, is_home=True)
        db.session.add(uc_sys)

        # 3. Create a normal user
        normal_user = User(username='normal_audit_user', email='normal_audit@example.com', status='active')
        normal_user.set_password('password')
        db.session.add(normal_user)
        db.session.flush()

        # Link normal user to normal_club
        uc_norm = UserClub(user_id=normal_user.id, club_id=2, is_home=True)
        db.session.add(uc_norm)
        db.session.commit()

    # A. Test normal user gets blocked
    client.post('/login', data={'username': 'normal_audit_user', 'password': 'password'})
    response = client.get('/api/audit-log')
    assert response.status_code == 403

    client.get('/logout')

    # B. Test sysadmin in normal club gets blocked
    client.post('/login', data={'username': 'sysadmin', 'password': 'password'})
    # Switch active club to normal club (ID=2)
    client.post('/clubs/2/enter')
    
    response = client.get('/api/audit-log')
    assert response.status_code == 403

    # C. Test sysadmin in super club (ID=1) is allowed
    # Switch active club back to super club
    client.post('/clubs/1/enter')
    response = client.get('/api/audit-log')
    assert response.status_code == 200

