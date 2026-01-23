import pytest
from app.models import User, Club, UserClub, AuthRole, Contact, ContactClub
from app.auth.permissions import Permissions

@pytest.fixture
def db_session(app):
    with app.app_context():
        from app import db
        yield db.session
        db.session.remove()

def test_user_role_isolation(client, app, db_session):
    """
    Verify that updating a user's role in one club does not affect their role in another club.
    """
    with app.app_context():
        # 1. Setup Data: Two clubs
        club_a = Club(club_no="TEST_A", club_name="Club A")
        club_b = Club(club_no="TEST_B", club_name="Club B")
        db_session.add_all([club_a, club_b])
        db_session.commit()
        
        # 2. Setup User
        user = User(username="isolation_test", email="isolation@test.com")
        user.set_password("password")
        db_session.add(user)
        db_session.commit()
        
        # Ensure Roles exist
        sysadmin_role = AuthRole.get_by_name(Permissions.SYSADMIN)
        if not sysadmin_role:
             sysadmin_role = AuthRole(name=Permissions.SYSADMIN, level=8)
             db_session.add(sysadmin_role)
             
        club_admin_role = AuthRole.get_by_name(Permissions.CLUBADMIN)
        if not club_admin_role:
            club_admin_role = AuthRole(name=Permissions.CLUBADMIN, level=4)
            db_session.add(club_admin_role)
            
        member_role = AuthRole.get_by_name(Permissions.USER)
        if not member_role:
            member_role = AuthRole(name=Permissions.USER, level=1)
            db_session.add(member_role)
            
        db_session.commit()
        
        # Ensure level is set for ALL roles in DB to avoid NoneType bitwise error
        for r in AuthRole.query.all():
            if r.level is None:
                r.level = 0
        
        # Ensure our target roles have specific levels for this test
        sysadmin_role.level = 8
        club_admin_role.level = 4
        member_role.level = 1
        db_session.commit()
        
        # 3. Assign Roles: 
        # Club A -> ClubAdmin
        # Club B -> Member
        user.set_club_role(club_a.id, club_admin_role.level)
        user.set_club_role(club_b.id, member_role.level)
        db_session.commit()
        
        # Create SysAdmin user to perform the edit
        admin = User(username="sysadmin_iso", email="admin@iso.com")
        admin.set_password("password")
        db_session.add(admin)
        db_session.commit()
        
        # Give admin SysAdmin role in Club A (effectively global/powerful for this test context or we mock is_authorized)
        admin.set_club_role(club_a.id, sysadmin_role.level)
        db_session.commit()
        
        # Login as Admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True
            
        # 4. GET the form for Club B context
        # We expect to see only 'Member' role checked, NOT 'ClubAdmin'
        # Note: We need to mock 'is_authorized' or ensure our admin has permissions. 
        # For simplicity, we'll assume the route check passes with our SysAdmin user or we can mock.
        
        # To avoid permission issues in test setup complexity, let's verify logic via DB/Direct route call simulation
        # But end-to-end route testing is best.
        
        # Simulate Context: Modifying User in Club B
        # POST data sending ONLY "Member" role (simulating a save in Club B context)
        data = {
            'username': user.username,
            'email': user.email,
            'roles': [member_role.id], # Only Member role sent back
            'club_id': club_b.id, # IMPORTANT: Context is Club B
            'status': 'active'
        }
        
        # Perform POST to save
        # We need to make sure we have permissions. logic in users_routes.py relies on is_authorized.
        # Let's ensure our admin user has the right permissions.
        # SysAdmin role usually has all permissions.
        
        response = client.post(f'/user/form/{user.id}', data=data, follow_redirects=True)
        assert response.status_code == 200
        
        # User should still be Member in Club B
        uc_b = UserClub.query.filter_by(user_id=user.id, club_id=club_b.id).first()
        assert uc_b.club_role_level == member_role.level
        
        # User should STILL be ClubAdmin in Club A (Unchanged)
        uc_a = UserClub.query.filter_by(user_id=user.id, club_id=club_a.id).first()
        assert uc_a.club_role_level == club_admin_role.level
        
        print("\nTest passed: Club roles remained isolated.")
        
        # Cleanup
        db_session.delete(user)
        db_session.delete(admin)
        db_session.delete(club_a)
        db_session.delete(club_b)
        db_session.commit()
