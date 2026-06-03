import pytest
from app import db
from app.models import User, Contact, AuthRole, Permission, UserClub, Club
from app.auth.permissions import Permissions
import json

@pytest.fixture(autouse=True)
def setup_roles_and_permissions(app, seeded_permissions):
    """Seed base roles and ensure permissions exist for testing."""
    with app.app_context():
        # Setup base roles
        roles = {}
        for name, level in [('SysAdmin', 8), ('ClubAdmin', 4), ('Operator', 3), ('Staff', 2), ('User', 1), ('Guest', 0)]:
            role = AuthRole.query.filter_by(name=name, club_id=None).first()
            if not role:
                role = AuthRole(name=name, description=f"{name} Role", level=level, club_id=None)
                db.session.add(role)
            roles[name] = role
        db.session.commit()

        # Add SETTINGS_EDIT to ClubAdmin
        edit_settings_perm = Permission.query.filter_by(name=Permissions.SETTINGS_EDIT).first()
        if not edit_settings_perm:
            edit_settings_perm = Permission(name=Permissions.SETTINGS_EDIT, description="Edit Settings", category="settings")
            db.session.add(edit_settings_perm)
            db.session.flush()

        club_admin_role = roles['ClubAdmin']
        if edit_settings_perm not in club_admin_role.permissions:
            club_admin_role.permissions.append(edit_settings_perm)
            
        # Add basic permissions to User template for copy verification
        view_agenda_perm = Permission.query.filter_by(name=Permissions.MEETING_VIEW_PUBLISHED).first()
        if not view_agenda_perm:
            view_agenda_perm = Permission(name=Permissions.MEETING_VIEW_PUBLISHED, description="View Agenda", category="agenda")
            db.session.add(view_agenda_perm)
            db.session.flush()
            
        user_role = roles['User']
        if view_agenda_perm not in user_role.permissions:
            user_role.permissions.append(view_agenda_perm)
            
        db.session.commit()
        AuthRole.clear_role_cache()

@pytest.fixture
def test_users(app, default_club):
    """Create test users: one with ClubAdmin role and one with normal User role."""
    with app.app_context():
        # 1. Club Admin User
        admin_contact = Contact(Name="Club Admin User", Email="clubadmin@example.com", Type="Member")
        db.session.add(admin_contact)
        db.session.flush()
        
        admin_user = User(username="clubadmin", email="clubadmin@example.com", status="active")
        admin_user.set_password("password")
        db.session.add(admin_user)
        db.session.flush()
        
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin', club_id=None).first()
        uc_admin = UserClub(
            user_id=admin_user.id,
            club_id=default_club.id,
            auth_role_id=club_admin_role.id,
            contact_id=admin_contact.id,
            is_home=True
        )
        db.session.add(uc_admin)
        
        # 2. Normal User
        normal_contact = Contact(Name="Normal User", Email="normal@example.com", Type="Member")
        db.session.add(normal_contact)
        db.session.flush()
        
        normal_user = User(username="normaluser", email="normal@example.com", status="active")
        normal_user.set_password("password")
        db.session.add(normal_user)
        db.session.flush()
        
        user_role = AuthRole.query.filter_by(name='User', club_id=None).first()
        uc_normal = UserClub(
            user_id=normal_user.id,
            club_id=default_club.id,
            auth_role_id=user_role.id,
            contact_id=normal_contact.id,
            is_home=True
        )
        db.session.add(uc_normal)
        
        db.session.commit()
        
        return {
            'admin_username': 'clubadmin',
            'normal_username': 'normaluser',
            'password': 'password',
            'admin_user_id': admin_user.id,
            'normal_user_id': normal_user.id
        }

def test_add_auth_role_permission_denied(app, client, auth, default_club, test_users):
    """Test that users without SETTINGS_EDIT permission cannot add a role."""
    with app.app_context():
        # Login as normal user
        auth.login(username=test_users['normal_username'], password=test_users['password'], club_id=default_club.id)
        
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'UnauthorizedRole',
            'description': 'Description',
            'template_role': 'User'
        })
        assert response.status_code == 403
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'permission denied' in data['message'].lower()

def test_add_auth_role_success_and_inheritance(app, client, auth, default_club, test_users):
    """Test successfully adding a role with correct club scoping, level, and permission inheritance."""
    with app.app_context():
        # Login as club admin
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=default_club.id)
        
        role_name = 'Custom Roster Manager'
        role_desc = 'Manages roster specific to this club'
        
        # Add new role based on the User template
        response = client.post('/api/settings/auth-roles/add', data={
            'name': role_name,
            'description': role_desc,
            'template_role': 'User'
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'added successfully' in data['message'].lower()
        
        # Verify in DB
        new_role = AuthRole.query.filter_by(name=role_name, club_id=default_club.id).first()
        assert new_role is not None
        assert new_role.description == role_desc
        
        # Verify Level Inheritance
        template_role = AuthRole.query.filter_by(name='User', club_id=None).first()
        assert new_role.level == template_role.level
        
        # Verify Permission Copying
        assert len(template_role.permissions) > 0
        for perm in template_role.permissions:
            assert perm in new_role.permissions

def test_add_auth_role_validation_failures(app, client, auth, default_club, test_users):
    """Test validation errors: empty name, non-existent template, and duplicates."""
    with app.app_context():
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=default_club.id)
        
        # 1. Empty name
        response = client.post('/api/settings/auth-roles/add', data={
            'name': '',
            'description': 'desc',
            'template_role': 'User'
        })
        assert response.status_code == 400
        assert 'name is required' in json.loads(response.data)['message'].lower()
        
        # 2. Non-existent template
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'CustomRole',
            'description': 'desc',
            'template_role': 'NonExistent'
        })
        assert response.status_code == 400
        assert 'template role' in json.loads(response.data)['message'].lower()
        
        # 3. Duplicate name (same name as a core system role)
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'Staff',
            'description': 'desc',
            'template_role': 'User'
        })
        assert response.status_code == 400
        assert 'already exists' in json.loads(response.data)['message'].lower()

def test_club_specific_name_scoping(app, client, auth, default_club, test_users):
    """Test that two different clubs can add roles with the same name, but duplicate in same club fails."""
    with app.app_context():
        # Setup second club
        club2 = Club(club_name="Second Test Club", club_no="999992")
        db.session.add(club2)
        db.session.commit()
        
        # Add admin_user to the second club as well
        admin_contact = Contact.query.filter_by(Email="clubadmin@example.com").first()
        admin_user = User.query.filter_by(username="clubadmin").first()
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin', club_id=None).first()
        
        uc_admin2 = UserClub(
            user_id=admin_user.id,
            club_id=club2.id,
            auth_role_id=club_admin_role.id,
            contact_id=admin_contact.id,
            is_home=False
        )
        db.session.add(uc_admin2)
        db.session.commit()
        
        # 1. Login to Club 1 and add role 'Co-VPE'
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=default_club.id)
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'Co-VPE',
            'description': 'Co-VPE for club 1',
            'template_role': 'User'
        })
        assert response.status_code == 200
        
        # Adding duplicate in same club (Club 1) should fail
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'Co-VPE',
            'description': 'duplicate Co-VPE',
            'template_role': 'User'
        })
        assert response.status_code == 400
        assert 'already exists' in json.loads(response.data)['message'].lower()
        
        # 2. Login to Club 2 and add role 'Co-VPE' (should succeed because scoped to club2)
        auth.logout()
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=club2.id)
        response = client.post('/api/settings/auth-roles/add', data={
            'name': 'Co-VPE',
            'description': 'Co-VPE for club 2',
            'template_role': 'User'
        })
        assert response.status_code == 200
        
        # Verify both exist in DB with separate club IDs
        role1 = AuthRole.query.filter_by(name='Co-VPE', club_id=default_club.id).first()
        role2 = AuthRole.query.filter_by(name='Co-VPE', club_id=club2.id).first()
        assert role1 is not None
        assert role2 is not None
        assert role1.id != role2.id

def test_delete_auth_role_blocks_core_roles(app, client, auth, default_club, test_users):
    """Test that core system roles (where club_id is None) cannot be deleted."""
    with app.app_context():
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=default_club.id)
        
        staff_role = AuthRole.query.filter_by(name='Staff', club_id=None).first()
        assert staff_role is not None
        
        response = client.post(f'/api/settings/auth-roles/delete/{staff_role.id}')
        assert response.status_code == 400
        assert 'cannot delete core' in json.loads(response.data)['message'].lower()

def test_delete_auth_role_permissions_and_scoping(app, client, auth, default_club, test_users):
    """Test that users must have SETTINGS_EDIT and role must belong to current club context to delete."""
    with app.app_context():
        # Setup second club
        club2 = Club(club_name="Second Test Club", club_no="999992")
        db.session.add(club2)
        db.session.commit()
        
        # Create a custom role in default_club
        custom_role = AuthRole(name='TemporaryRole', description='desc', level=1, club_id=default_club.id)
        db.session.add(custom_role)
        db.session.commit()
        role_id = custom_role.id
        
        # 1. Normal user without permission receives 403
        auth.login(username=test_users['normal_username'], password=test_users['password'], club_id=default_club.id)
        response = client.post(f'/api/settings/auth-roles/delete/{role_id}')
        assert response.status_code == 403
        
        # 2. Login to Club 2 as admin (which doesn't own this role) and attempt delete. Should return 404.
        admin_contact = Contact.query.filter_by(Email="clubadmin@example.com").first()
        admin_user = User.query.filter_by(username="clubadmin").first()
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin', club_id=None).first()
        
        uc_admin2 = UserClub(
            user_id=admin_user.id,
            club_id=club2.id,
            auth_role_id=club_admin_role.id,
            contact_id=admin_contact.id,
            is_home=False
        )
        db.session.add(uc_admin2)
        db.session.commit()
        
        auth.logout()
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=club2.id)
        response = client.post(f'/api/settings/auth-roles/delete/{role_id}')
        assert response.status_code == 404
        assert 'not found' in json.loads(response.data)['message'].lower()

def test_delete_auth_role_and_bulk_detaching(app, client, auth, default_club, test_users):
    """Test that deleting a custom role successfully deletes the role and reassigns users to 'User'."""
    with app.app_context():
        # Create a custom role in default_club
        custom_role = AuthRole(name='SpecialMember', description='Special custom role', level=1, club_id=default_club.id)
        db.session.add(custom_role)
        db.session.commit()
        role_id = custom_role.id
        
        # Assign the normal user to this custom role in default_club
        uc_normal = UserClub.query.filter_by(user_id=test_users['normal_user_id'], club_id=default_club.id).first()
        assert uc_normal is not None
        uc_normal.auth_role_id = role_id
        db.session.commit()
        
        # Login as admin
        auth.login(username=test_users['admin_username'], password=test_users['password'], club_id=default_club.id)
        
        # Delete custom role
        response = client.post(f'/api/settings/auth-roles/delete/{role_id}')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'deleted' in data['message'].lower()
        
        # Verify role is deleted
        deleted_role = db.session.get(AuthRole, role_id)
        assert deleted_role is None
        
        # Verify user is bulk detached and reassigned to core 'User' role
        db.session.expire(uc_normal)
        user_role = AuthRole.query.filter_by(name='User', club_id=None).first()
        assert uc_normal.auth_role_id == user_role.id


def test_direct_permission_check(app, default_club, test_users):
    with app.app_context():
        admin_user = User.query.filter_by(username="clubadmin").first()
        assert admin_user.has_club_permission(Permissions.SETTINGS_EDIT, default_club.id) is True
