import pytest
from datetime import datetime, timedelta, date
from app.models import Club, User, AuthRole, UserClub, Contact, Message
from app.auth.permissions import Permissions

@pytest.fixture
def test_user(app, default_club):
    """Create a regular user for testing."""
    from app.models import db, Contact
    with app.app_context():
        user = User.query.filter_by(email='dir_user@example.com').first()
        if not user:
            user = User(username='dir_user', email='dir_user@example.com', password_hash='hash')
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        
        contact = Contact.query.filter_by(Email=user.email).first()
        if not contact:
            contact = Contact(Name='Dir User', Email=user.email, first_name='Dir', last_name='User')
            db.session.add(contact)
            db.session.commit()
            db.session.refresh(contact)
            
        return user

@pytest.fixture
def admin_user(app, default_club):
    """Create a sysadmin user for testing."""
    from app.models import db
    with app.app_context():
        user = User.query.filter_by(username='sysadmin').first()
        if not user:
            user = User(username='sysadmin', email='sysadmin@test.com', password_hash='hash')
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        return user

def test_club_status_filtering(client, test_user, app):
    """Test that super status clubs (like Tech Support) are filtered out of the directory."""
    from app.models import db
    with app.app_context():
        # Clean any super / active clubs
        Club.query.filter(Club.club_no.in_(['111', '222'])).delete()
        
        club_active = Club(club_no='111', club_name='Active Club', status='active')
        club_super = Club(club_no='222', club_name='Tech Support Club', status='super')
        db.session.add(club_active)
        db.session.add(club_super)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True

    response = client.get('/clubs')
    assert response.status_code == 200
    assert b'Active Club' in response.data
    assert b'Tech Support Club' not in response.data

def test_favorite_club_toggle(client, test_user, app):
    """Test toggling a club as favorite via AJAX."""
    from app.models import db
    with app.app_context():
        club = Club(club_no='333', club_name='Fav Club', status='active')
        db.session.add(club)
        db.session.commit()
        club_id = club.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True

    # 1. Favorite
    response = client.post(f'/clubs/{club_id}/favorite', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['is_favorite'] is True

    with app.app_context():
        u = db.session.get(User, test_user.id)
        c = db.session.get(Club, club_id)
        assert c in u.favorite_clubs.all()

    # 2. Unfavorite
    response = client.post(f'/clubs/{club_id}/favorite', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json['is_favorite'] is False

    with app.app_context():
        u = db.session.get(User, test_user.id)
        c = db.session.get(Club, club_id)
        assert c not in u.favorite_clubs.all()



def test_club_directory_sorting(client, test_user, app):
    """Test state-based sorting logic: Home -> Joined -> Favorite -> Unjoined (sub-sorted by next meeting date)."""
    from app.models import db, Meeting, UserClub
    with app.app_context():
        # Clean any preexisting test clubs
        Club.query.filter(Club.club_no.in_(['10', '20', '30', '40', '50'])).delete()
        
        c1 = Club(club_no='10', club_name='Club Home', status='active')
        c2 = Club(club_no='20', club_name='Club Joined Earlier Meeting', status='active')
        c3 = Club(club_no='30', club_name='Club Joined Later Meeting', status='active')
        c4 = Club(club_no='40', club_name='Club Favorite', status='active')
        c5 = Club(club_no='50', club_name='Club Other', status='active')
        
        db.session.add_all([c1, c2, c3, c4, c5])
        db.session.commit()
        
        # Link user home & joined
        db.session.add(UserClub(user_id=test_user.id, club_id=c1.id, is_home=True))
        db.session.add(UserClub(user_id=test_user.id, club_id=c2.id, is_home=False))
        db.session.add(UserClub(user_id=test_user.id, club_id=c3.id, is_home=False))
        
        # Add c4 to favorites
        u = db.session.get(User, test_user.id)
        u.favorite_clubs.append(c4)
        
        # Setup meetings (c2 has earlier meeting than c3)
        m2 = Meeting(club_id=c2.id, Meeting_Number=101, Meeting_Date=datetime.now().date() + timedelta(days=2), status='not started')
        m3 = Meeting(club_id=c3.id, Meeting_Number=102, Meeting_Date=datetime.now().date() + timedelta(days=5), status='not started')
        db.session.add_all([m2, m3])
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True

    response = client.get('/clubs')
    assert response.status_code == 200
    
    # Verify order in output body by finding indices
    content = response.data.decode('utf-8')
    
    idx_home = content.find('Club Home')
    idx_joined_early = content.find('Club Joined Earlier Meeting')
    idx_joined_later = content.find('Club Joined Later Meeting')
    idx_favorite = content.find('Club Favorite')
    idx_other = content.find('Club Other')
    
    # All must exist in content
    assert idx_home != -1
    assert idx_joined_early != -1
    assert idx_joined_later != -1
    assert idx_favorite != -1
    assert idx_other != -1
    
    # Assert correct ordering: Home < Joined Early < Joined Later < Favorite < Other
    assert idx_home < idx_joined_early
    assert idx_joined_early < idx_joined_later
    assert idx_joined_later < idx_favorite
    assert idx_favorite < idx_other


def test_enter_club_flow(client, test_user, app):
    """Test entering a club context. If not a member, the user takes the Guest role."""
    from app.models import db, UserClub, AuthRole
    with app.app_context():
        # Clean any preexisting test clubs
        Club.query.filter(Club.club_no == '777').delete()
        
        # Ensure Guest role exists
        guest_role = AuthRole.query.filter_by(name='Guest').first()
        if not guest_role:
            guest_role = AuthRole(name='Guest', level=0)
            db.session.add(guest_role)
            
        club = Club(club_no='777', club_name='Test Enter Club', status='active')
        db.session.add(club)
        db.session.commit()
        club_id = club.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True

    # 1. Post to enter club
    response = client.post(f'/clubs/{club_id}/enter', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'agenda' in response.json['redirect_url']

    # 2. Verify in-database Guest role membership created
    with app.app_context():
        uc = UserClub.query.filter_by(user_id=test_user.id, club_id=club_id).first()
        assert uc is not None
        assert uc.auth_role.name == 'Guest'

    # 3. Verify session contains the club ID
    with client.session_transaction() as sess:
        assert sess['current_club_id'] == club_id


def test_cancel_join_request(client, test_user, admin_user, app):
    """Test canceling a pending join request."""
    from app.models import db, Club, Message
    with app.app_context():
        Club.query.filter(Club.club_no == '888').delete()
        club = Club(club_no='888', club_name='Test Cancel Club', status='active')
        db.session.add(club)
        db.session.commit()
        club_id = club.id
        
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
        
    # 1. Request to Join (sysadmin exists as fallback recipient)
    response = client.post(f'/clubs/{club_id}/request_join', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    
    # Verify message was created
    with app.app_context():
        msgs = Message.query.filter(
            Message.sender_id == test_user.id,
            Message.body.like(f"%[JOIN_REQUEST:{test_user.id}:{club_id}]%")
        ).all()
        assert len(msgs) > 0
        for m in msgs:
            assert "[Responded:" not in m.body
            
    # 2. Cancel the join request
    response = client.post(f'/clubs/{club_id}/cancel_join', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'cancelled' in response.json['message'].lower()
    
    # Verify message has been marked as Responded: CANCELLED
    with app.app_context():
        msgs = Message.query.filter(
            Message.sender_id == test_user.id,
            Message.body.like(f"%[JOIN_REQUEST:{test_user.id}:{club_id}]%")
        ).all()
        for m in msgs:
            assert "[Responded: CANCELLED]" in m.body
            assert m.read is True


def test_guest_userclub_does_not_block_join(client, test_user, admin_user, app):
    """A UserClub row with the Guest role is a guest-visit record, not a
    membership. The /clubs page shows the Join button for these users, and
    request_join must NOT reject the click with 'already a member' — that
    would leave the page and the route out of sync."""
    from app.models import db, Club, UserClub
    with app.app_context():
        Club.query.filter(Club.club_no == '777').delete()
        club = Club(club_no='777', club_name='Guest Visit Club', status='active')
        db.session.add(club)
        db.session.commit()
        club_id = club.id

        guest_role = AuthRole.query.filter_by(name='Guest').first()
        if not guest_role:
            guest_role = AuthRole(name='Guest', level=0)
            db.session.add(guest_role)
            db.session.flush()
        # No non-Guest membership for this user in this club.
        UserClub.query.filter_by(user_id=test_user.id, club_id=club_id).delete()
        db.session.add(UserClub(
            user_id=test_user.id, club_id=club_id,
            auth_role_id=guest_role.id, is_home=False,
        ))
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True

    # /clubs must render a Join button for this club (template treats Guest
    # as non-member).
    response = client.get('/clubs')
    assert response.status_code == 200
    assert f'requestJoinClub(this, {club_id})'.encode() in response.data
    assert f'btn-cancel-request.*onclick="cancelJoinRequest\\(this, {club_id}\\)'.encode() \
        not in response.data

    # request_join must accept the request rather than returning
    # 'You are already a member of this club.'.
    response = client.post(f'/clubs/{club_id}/request_join', json={})
    assert response.status_code == 200
    assert response.json['success'] is True


def test_request_quit_club_flow(client, test_user, admin_user, app):
    """Test requesting to quit a club and cancelling the request."""
    from app.models import db, Club, UserClub, Message
    with app.app_context():
        Club.query.filter(Club.club_no == '999').delete()
        club = Club(club_no='999', club_name='Test Quit Club', status='active')
        db.session.add(club)
        db.session.commit()
        club_id = club.id
        
        # Link user as a member
        db.session.add(UserClub(user_id=test_user.id, club_id=club_id, is_home=False))
        db.session.commit()
        
    with client.session_transaction() as sess:
        sess['_user_id'] = str(test_user.id)
        sess['_fresh'] = True
        
    # 1. Send quit request (route still exists for back-end/admin flows, but
    #    the /clubs page no longer surfaces a Quit button).
    response = client.post(f'/clubs/{club_id}/request_quit', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'request to leave the club has been sent' in response.json['message']

    # The clubs page must not render a "Cancel Quit" or "Quit" button.
    response = client.get('/clubs')
    assert response.status_code == 200
    assert f'cancelQuitRequest(this, {club_id})'.encode() not in response.data
    assert f'requestQuitClub(this, {club_id})'.encode() not in response.data

    # 2. Cancel the quit request
    response = client.post(f'/clubs/{club_id}/cancel_quit', json={})
    assert response.status_code == 200
    assert response.json['success'] is True
    assert 'quit request has been cancelled' in response.json['message'].lower()

    # Verify message has been marked as Responded: CANCELLED
    with app.app_context():
        msgs = Message.query.filter(
            Message.sender_id == test_user.id,
            Message.body.like("%[Responded: CANCELLED]%")
        ).all()
        assert len(msgs) > 0
        for m in msgs:
            assert m.read is True

    # Clubs page still does not render a Quit button.
    response = client.get('/clubs')
    assert response.status_code == 200
    assert f'cancelQuitRequest(this, {club_id})'.encode() not in response.data
    assert f'requestQuitClub(this, {club_id})'.encode() not in response.data





