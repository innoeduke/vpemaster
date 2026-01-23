
import pytest
from app.models import User, Club, Message, UserClub

def test_join_request_flow(client, app, default_club):
    with app.app_context():
        from app import db
        # 1. Setup: Create another club and 2 users
        club1 = default_club
        club2 = Club(club_name="Target Club", club_no="999888")
        db.session.add(club2)
        db.session.commit()
        
        # Admin User (in Club 1)
        admin_user = User(username="admin_join", email="admin_join@test.com")
        admin_user.set_password("password")
        db.session.add(admin_user)
        db.session.commit()
        
        # Link admin to Club 1 as Admin
        db.session.add(UserClub(user_id=admin_user.id, club_id=club1.id, club_role_level=1))
        
        # Target User (in Club 2)
        target_user = User(username="target_join", email="target_join@test.com", first_name="Target", last_name="User")
        target_user.set_password("password")
        db.session.add(target_user)
        db.session.commit()
        
        db.session.add(UserClub(user_id=target_user.id, club_id=club2.id, club_role_level=1))
        db.session.commit()
        
        admin_id = admin_user.id
        target_id = target_user.id
        club1_id = club1.id

    # 2. Login as Admin
    with client:
        login_resp = client.post('/login', data={'username': 'admin_join', 'password': 'password', 'club_names': club1_id}, follow_redirects=True)
        assert login_resp.status_code == 200
        if b'Invalid username or password' in login_resp.data:
            pytest.fail("Login failed")
        
        # 3. Request Join
        response = client.post('/user/request_join', json={
            'target_user_id': target_id,
            'club_id': club1_id
        })
        if response.status_code != 200:
             pytest.fail(f"Request Join Failed: {response.status_code}, {response.data}")
        assert response.status_code == 200
        assert response.json['success'] is True
        
        # Verify Message
        with app.app_context():
            msg = Message.query.filter_by(recipient_id=target_id).first()
            assert msg is not None
            assert f"[CLUB_ID:{club1_id}]" in msg.body
            assert "Invitation to join Test Club" in msg.subject
            message_id = msg.id

    # 4. Login as Target User
    with client:
        # Logout Admin first
        client.get('/logout', follow_redirects=True)
        login_resp = client.post('/login', data={'username': 'target_join', 'password': 'password', 'club_names': club2.id}, follow_redirects=True)
        assert login_resp.status_code == 200
        if b'Invalid username or password' in login_resp.data:
            pytest.fail("Target User Login failed")
            
        # 5. Respond Join (Accept)
        response = client.post('/user/respond_join', json={
            'message_id': message_id,
            'action': 'join'
        })
        assert response.status_code == 200
        assert response.json['success'] is True
        
        # Verify User Added to Club 1
        with app.app_context():
            uc = UserClub.query.filter_by(user_id=target_id, club_id=club1_id).first()
            assert uc is not None
            
            # Verify Reply Message
            reply = Message.query.filter_by(recipient_id=admin_id).order_by(Message.id.desc()).first()
            assert reply is not None
            assert "accepted your request" in reply.body
            
            # Verify Original Message Updated
            orig_msg = db.session.get(Message, message_id)
            assert "[Responded: JOIN]" in orig_msg.body
            assert "[CLUB_ID:" not in orig_msg.body

def test_join_request_reject(client, app, default_club):
     with app.app_context():
        from app import db
        club1 = default_club
        
        admin_user = User(username="admin_rejector", email="admin_r@test.com")
        admin_user.set_password("password")
        db.session.add(admin_user)
        
        target_user = User(username="target_rejector", email="target_r@test.com", first_name="Target", last_name="Rejector")
        target_user.set_password("password")
        db.session.add(target_user)
        db.session.commit()
        
        db.session.add(UserClub(user_id=admin_user.id, club_id=club1.id, club_role_level=1))
        
        admin_id = admin_user.id
        target_id = target_user.id
        club1_id = club1.id

     # Login as Admin
     with client:
        client.post('/login', data={'username': 'admin_rejector', 'password': 'password', 'club_id': club1_id})
        client.post('/user/request_join', json={'target_user_id': target_id, 'club_id': club1_id})
        
     # Get Message ID
     with app.app_context():
         msg = Message.query.filter_by(recipient_id=target_id).order_by(Message.id.desc()).first()
         message_id = msg.id

     # Login as Target
     with client:
        client.get('/logout', follow_redirects=True)
        client.post('/login', data={'username': 'target_rejector', 'password': 'password'})
        
        # Respond GET

        response = client.post('/user/respond_join', json={
            'message_id': message_id,
            'action': 'reject'
        })
        assert response.status_code == 200
        
        # Verify NOT added
        with app.app_context():
            uc = UserClub.query.filter_by(user_id=target_id, club_id=club1_id).first()
            assert uc is None
            
            # Verify Reply
            reply = Message.query.filter_by(recipient_id=admin_id).order_by(Message.id.desc()).first()
            assert "declined to join" in reply.body
