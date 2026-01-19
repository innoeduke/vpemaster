import pytest
from app.models import User, Club, UserClub, Contact, ContactClub

@pytest.fixture
def db_session(app):
    with app.app_context():
        from app import db
        yield db.session
        db.session.remove()

def test_contact_isolation(client, app, db_session):
    """
    Verify that adding the same user to two clubs creates TWO separate Contact records.
    """
    with app.app_context():
        # Setup: Two Clubs
        club_a = Club(club_no="ISO_A", club_name="Isolation Club A")
        club_b = Club(club_no="ISO_B", club_name="Isolation Club B")
        db_session.add_all([club_a, club_b])
        db_session.commit()
        
        # Setup: Roles
        from app.models import AuthRole
        from app.auth.permissions import Permissions
        sysadmin_role = AuthRole.get_by_name(Permissions.SYSADMIN)
        if not sysadmin_role:
            sysadmin_role = AuthRole(name=Permissions.SYSADMIN, level=8)
            db_session.add(sysadmin_role)
        member_role = AuthRole.get_by_name(Permissions.USER)
        if not member_role:
            member_role = AuthRole(name=Permissions.USER, level=1)
            db_session.add(member_role)
        db_session.commit()

        # Admin User
        admin = User(username="admin_iso", email="admin@test.com")
        admin.set_password("password")
        db_session.add(admin)
        db_session.commit()
        admin.set_club_role(club_a.id, sysadmin_role.level)
        db_session.commit()

        # Log in
        client.post('/login', data={'username': 'admin_iso', 'password': 'password', 'club_names': club_a.id})
        
        # Create User
        user = User(username="contact_iso_test", email="iso@test.com")
        user.set_password("password")
        db_session.add(user)
        db_session.commit()
        
        # 1. Add User to Club A -> Should create Contact A
        user.ensure_contact(full_name="Iso User", email="iso@test.com", club_id=club_a.id)
        db_session.commit()
        
        # Verify Contact A
        contact_a = user.get_contact(club_id=club_a.id)
        assert contact_a is not None
        assert contact_a.Email == "iso@test.com"
        
        # Verify Linkage
        cc_a = ContactClub.query.filter_by(contact_id=contact_a.id, club_id=club_a.id).first()
        assert cc_a is not None
        
        # 2. Add User to Club B -> Should create Contact B (DIFFERENT ID)
        # Previously, this would reuse Contact A based on email match.
        # Now, it should create a NEW contact because Contact A is not linked to Club B.
        user.ensure_contact(full_name="Iso User", email="iso@test.com", club_id=club_b.id)
        db_session.commit()
        
        contact_b = user.get_contact(club_id=club_b.id)
        assert contact_b is not None
        assert contact_b.Email == "iso@test.com"
        
        # CRITICAL ASSERTION: IDs must be different
        print(f"Contact A ID: {contact_a.id}, Contact B ID: {contact_b.id}")
        assert contact_a.id != contact_b.id
        
        # 3. Simulate UI-style addition via POST
        # Suppose a user exists in Club A with Contact A.
        # We now use the 'user_form' to add them to Club C.
        club_c = Club(club_no="ISO_C", club_name="Isolation Club C")
        db_session.add(club_c)
        db_session.commit()
        
        # Simulate the form submission from the browser
        # Note: We pass NO contact_id to simulate the fix where new clubs get no pre-population
        response = client.post(f'/user/form/{user.id}?club_id={club_c.id}', data={
            'username': user.username,
            'email': 'iso@test.com',
            'first_name': 'Iso',
            'last_name': 'User',
            'roles': '1', # Member
            'club_id': club_c.id
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify Contact C exists and is DIFFERENT from A and B
        uc_c = UserClub.query.filter_by(user_id=user.id, club_id=club_c.id).first()
        assert uc_c is not None
        contact_c = uc_c.contact
        assert contact_c is not None
        assert contact_c.id not in [contact_a.id, contact_b.id]
        
        print(f"Contact C ID: {contact_c.id} (Unique)")
        
        # 4. Final check: verify that a maliciously passed contact_id from another club is IGNORED
        # Simulate someone trying to force link Contact A to Club D
        club_d = Club(club_no="ISO_D", club_name="Isolation Club D")
        db_session.add(club_d)
        db_session.commit()
        
        response = client.post(f'/user/form/{user.id}?club_id={club_d.id}', data={
            'username': user.username,
            'contact_id': contact_a.id, # Attempted leak!
            'email': 'iso@test.com',
            'first_name': 'Iso',
            'last_name': 'User',
            'roles': '1',
            'club_id': club_d.id
        }, follow_redirects=True)
        
        uc_d = UserClub.query.filter_by(user_id=user.id, club_id=club_d.id).first()
        assert uc_d.contact_id != contact_a.id # SHOUD NOT BE REUSED
        assert uc_d.contact_id is not None
        
        print(f"Malicious link prevented. New contact created for Club D: {uc_d.contact_id}")

        print("\nTest passed: Contacts are strictly isolated per club across all entry points.")
        
        # Cleanup
        db_session.delete(user)
        db_session.delete(club_a)
        db_session.delete(club_b)
        db_session.delete(club_c)
        db_session.delete(club_d)
        db_session.delete(contact_a)
        db_session.delete(contact_b)
        db_session.delete(contact_c)
        db_session.delete(uc_d.contact)
        db_session.commit()
