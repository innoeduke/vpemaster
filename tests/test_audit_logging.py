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
