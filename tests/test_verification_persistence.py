import pytest
from app.models import VerificationTask, db
from unittest.mock import patch, MagicMock
import time
from app.auth.permissions import Permissions

def test_verification_task_persistence(client, app, auth, default_club):
    """Test that verification tasks are persisted in the DB and pollable."""
    # 1. Setup user with permission
    from app.models import User, AuthRole, UserClub, Permission
    with app.app_context():
        user = User.query.filter_by(username='testadmin').first()
        if not user:
            user = User(username='testadmin', email='testadmin@example.com', status='active')
            user.set_password('password')
            db.session.add(user)
            db.session.flush()
            
            role = AuthRole.query.filter_by(name='AdminRole').first()
            if not role:
                role = AuthRole(name='AdminRole', level=10)
                db.session.add(role)
                db.session.flush()
            
            perm = Permission.query.filter_by(name=Permissions.SETTINGS_VIEW_ALL).first()
            if not perm:
                perm = Permission(name=Permissions.SETTINGS_VIEW_ALL, category='test')
                db.session.add(perm)
                db.session.flush()
            
            if perm not in role.permissions:
                role.permissions.append(perm)
            
            user.roles.append(role)
            uc = UserClub(user_id=user.id, club_id=default_club.id, club_role_level=role.level)
            db.session.add(uc)
            db.session.commit()

    # 2. Login as the newly created admin
    auth.login(username='testadmin', password='password')

    # 3. Mock blockchain service to control timing
    with patch('app.services.blockchain_service.verify_level') as mock_verify:
        mock_verify.return_value = {"verified": True, "tx_hash": "0x123", "block_number": 100}
        
        # We want to pause the background thread to check 'pending' status
        # but since it's a thread, we'll just check if it was created in DB
        
        with app.app_context():
            # Ensure DB is clean
            VerificationTask.query.delete()
            db.session.commit()

        # 3. Submit verification
        params = {
            "member_id": "PN-12345678",
            "path_name": "Engaging Humor",
            "level": 1
        }
        response = client.post('/tools/validator', json=params)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        task_id = data['task_id']

        # 4. Verify task exists in DB immediately
        with app.app_context():
            task = VerificationTask.query.get(task_id)
            assert task is not None
            assert task.status in ['pending', 'done'] # Might be done already if fast
            assert task.params['member_id'] == "PN-12345678"

        # 5. Poll status via API
        response = client.get(f'/tools/validator/status/{task_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['status'] in ['pending', 'done']

        # 6. Wait for background thread to finish (it's mocked, so should be fast)
        # We give it a small grace period
        attempts = 0
        while attempts < 10:
            response = client.get(f'/tools/validator/status/{task_id}')
            data = response.get_json()
            if data['status'] == 'done':
                break
            time.sleep(0.5)
            attempts += 1
        
        assert data['status'] == 'done'
        assert data['result']['verified'] is True

def test_cleanup_old_tasks(app):
    """Test that old tasks are cleaned up."""
    with app.app_context():
        # Create an old task
        old_task = VerificationTask(
            id="old-task",
            status="done",
            created_at=time.time() - 700  # Older than 600s
        )
        # Create a new task
        new_task = VerificationTask(
            id="new-task",
            status="pending",
            created_at=time.time()
        )
        db.session.add(old_task)
        db.session.add(new_task)
        db.session.commit()

        from app.tools_routes import _cleanup_old_tasks
        _cleanup_old_tasks()

        assert VerificationTask.query.get("old-task") is None
        assert VerificationTask.query.get("new-task") is not None
