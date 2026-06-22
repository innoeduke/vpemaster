"""Tests for program blueprint and template/enrollment administration API endpoints."""
import json
import pytest
from app import db
from app.auth.permissions import Permissions
from app.models import Club, User, AuthRole, UserClub, Contact, Planner
from app.models.program import Program, ProgramTask, ProgramEnrollment
from app.models.role_permission import RolePermission
from app.models.permission import Permission


@pytest.fixture
def auth_setup(app, default_club, seeded_permissions):
    """Set up roles, permissions, and test users with different access levels."""
    with app.app_context():
        # Get permissions
        perm_self = Permission.query.filter_by(name=Permissions.PROGRAMS_SELF).first()
        perm_manage = Permission.query.filter_by(name=Permissions.PROGRAMS_MANAGE).first()
        
        if not perm_self:
            perm_self = Permission(name=Permissions.PROGRAMS_SELF, category='test')
            db.session.add(perm_self)
        if not perm_manage:
            perm_manage = Permission(name=Permissions.PROGRAMS_MANAGE, category='test')
            db.session.add(perm_manage)
        db.session.commit()

        # Create roles
        admin_role = AuthRole.query.filter_by(name="ClubAdmin").first()
        if not admin_role:
            admin_role = AuthRole(name="ClubAdmin", level=50)
            db.session.add(admin_role)
        
        member_role = AuthRole.query.filter_by(name="Member").first()
        if not member_role:
            member_role = AuthRole(name="Member", level=1)
            db.session.add(member_role)
        db.session.commit()

        # Associate permissions with roles
        if perm_self not in member_role.permissions:
            member_role.permissions.append(perm_self)
        if perm_self not in admin_role.permissions:
            admin_role.permissions.append(perm_self)
        if perm_manage not in admin_role.permissions:
            admin_role.permissions.append(perm_manage)
        db.session.commit()

        # Create Admin user
        admin = User.query.filter_by(username="admin_user").first()
        if not admin:
            admin = User(username="admin_user", email="admin@example.com", status="active")
            admin.set_password("password")
            db.session.add(admin)
            db.session.flush()
            
            admin_contact = Contact(Name="Admin Name", Type="Member", Email="admin@example.com")
            db.session.add(admin_contact)
            db.session.flush()
            
            uc_admin = UserClub(user_id=admin.id, club_id=default_club.id, contact_id=admin_contact.id, auth_role_id=admin_role.id)
            db.session.add(uc_admin)
            db.session.commit()

        # Create Member user (mentee)
        member = User.query.filter_by(username="member_user").first()
        if not member:
            member = User(username="member_user", email="member@example.com", status="active")
            member.set_password("password")
            db.session.add(member)
            db.session.flush()
            
            member_contact = Contact(Name="Member Name", Type="Member", Email="member@example.com")
            db.session.add(member_contact)
            db.session.flush()
            
            uc_member = UserClub(user_id=member.id, club_id=default_club.id, contact_id=member_contact.id, auth_role_id=member_role.id)
            db.session.add(uc_member)
            db.session.commit()

        # Create Mentor user
        mentor = User.query.filter_by(username="mentor_user").first()
        if not mentor:
            mentor = User(username="mentor_user", email="mentor@example.com", status="active")
            mentor.set_password("password")
            db.session.add(mentor)
            db.session.flush()
            
            mentor_contact = Contact(Name="Mentor Name", Type="Member", Email="mentor@example.com")
            db.session.add(mentor_contact)
            db.session.flush()
            
            uc_mentor = UserClub(user_id=mentor.id, club_id=default_club.id, contact_id=mentor_contact.id, auth_role_id=member_role.id)
            db.session.add(uc_mentor)
            db.session.commit()

        return {
            "admin": User.query.filter_by(username="admin_user").first(),
            "member": User.query.filter_by(username="member_user").first(),
            "mentor": User.query.filter_by(username="mentor_user").first()
        }


def test_programs_admin_page_authorization(client, default_club, auth_setup):
    """Test that only admins can access the template administration page."""
    # Try as regular member
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["member"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/programs')
    assert response.status_code == 403

    # Try as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["admin"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/programs')
    assert response.status_code == 200


def test_template_crud_endpoints(client, default_club, auth_setup):
    """Test template CRUD REST endpoints (GET, POST, PUT, DELETE)."""
    # 1. List templates (initially empty)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["member"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/api/programs')
    assert response.status_code == 200
    assert json.loads(response.data) == []

    # 2. Create template (forbidden for member)
    response = client.post('/api/programs', json={"name": "New Program"})
    assert response.status_code == 403

    # Login as admin
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["admin"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    # Create template (successful)
    response = client.post('/api/programs', json={
        "name": "Orientation",
        "description": "New member onboarding flow",
        "is_active": True,
        "display_order": 1
    })
    assert response.status_code == 201
    res_data = json.loads(response.data)
    assert res_data["success"] is True
    pid = res_data["id"]

    # 3. Update template
    response = client.put(f'/api/programs/{pid}', json={
        "name": "Updated Orientation",
        "description": "Updated description",
        "is_active": True,
        "display_order": 2
    })
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

    # Verify update in GET
    response = client.get('/api/programs')
    programs = json.loads(response.data)
    assert len(programs) == 1
    assert programs[0]["name"] == "Updated Orientation"
    assert programs[0]["display_order"] == 2

    # 4. Soft Delete (Deactivate) template
    response = client.delete(f'/api/programs/{pid}')
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

    # Verify soft-deleted template is inactive and doesn't return in get_programs API
    response = client.get('/api/programs')
    assert json.loads(response.data) == []


def test_task_crud_endpoints(client, default_club, auth_setup):
    """Test task CRUD REST endpoints inside a program template."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["admin"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    # Setup program template
    response = client.post('/api/programs', json={"name": "Tasks Test Program"})
    pid = json.loads(response.data)["id"]

    # 1. Create tasks
    response = client.post(f'/api/programs/{pid}/tasks', json={
        "title": "Ice Breaker Speech",
        "description": "Deliver your first speech",
        "phase_label": "Month 1",
        "completion_type": "ice_breaker",
        "is_required": True,
        "display_order": 1
    })
    assert response.status_code == 201
    tid = json.loads(response.data)["id"]

    # 2. List tasks
    response = client.get(f'/api/programs/{pid}/tasks')
    assert response.status_code == 200
    tasks = json.loads(response.data)
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Ice Breaker Speech"

    # 3. Update task
    response = client.put(f'/api/programs/{pid}/tasks/{tid}', json={
        "title": "Updated Ice Breaker",
        "description": "Deliver your first speech updated",
        "phase_label": "Month 1",
        "completion_type": "ice_breaker",
        "is_required": True,
        "display_order": 1
    })
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

    # 4. Delete task
    response = client.delete(f'/api/programs/{pid}/tasks/{tid}')
    assert response.status_code == 200
    assert json.loads(response.data)["success"] is True

    # Verify delete
    response = client.get(f'/api/programs/{pid}/tasks')
    assert json.loads(response.data) == []


def test_enrollments_endpoints_and_visibility(client, default_club, auth_setup):
    """Test enrollment creation, retrieval, and visibility filtering rules."""
    # Login as admin to set up program template and enroll member
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["admin"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.post('/api/programs', json={"name": "Enrollment Program"})
    pid = json.loads(response.data)["id"]

    response = client.post(f'/api/programs/{pid}/tasks', json={
        "title": "Orientation Check",
        "completion_type": "manual",
        "is_required": True
    })
    
    # 1. Create Enrollment
    response = client.post('/api/program-enrollments', json={
        "program_id": pid,
        "user_id": auth_setup["member"].id,
        "mentor_user_id": auth_setup["mentor"].id,
        "notes": "Test Enrollment"
    })
    assert response.status_code == 201
    eid = json.loads(response.data)["id"]

    # 2. Visibility Matrix Test: Retrieve enrollments with different accounts
    # Member user (should see own enrollment only)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["member"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/api/program-enrollments')
    enrollments = json.loads(response.data)
    assert len(enrollments) == 1
    assert enrollments[0]["id"] == eid
    assert enrollments[0]["mentee"]["id"] == auth_setup["member"].id

    # Mentor user (should see their mentee's enrollment)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["mentor"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/api/program-enrollments')
    enrollments = json.loads(response.data)
    assert len(enrollments) == 1
    assert enrollments[0]["id"] == eid
    assert enrollments[0]["mentee"]["id"] == auth_setup["member"].id

    # Admin user (should see all enrollments)
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["admin"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.get('/api/program-enrollments')
    enrollments = json.loads(response.data)
    assert len(enrollments) == 1

    # 3. Get detailed enrollment details
    response = client.get(f'/api/program-enrollments/{eid}')
    assert response.status_code == 200
    details = json.loads(response.data)
    assert details["notes"] == "Test Enrollment"
    assert len(details["tasks"]) == 1
    planner_id = details["tasks"][0]["planner_id"]

    # 4. Toggle manual task completion
    # Regular member toggling
    with client.session_transaction() as sess:
        sess['_user_id'] = str(auth_setup["member"].id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    response = client.post(f'/api/program-enrollments/{eid}/tasks/{planner_id}/toggle')
    assert response.status_code == 200
    assert json.loads(response.data)["status"] == "completed"

    # Toggle again to revert
    response = client.post(f'/api/program-enrollments/{eid}/tasks/{planner_id}/toggle')
    assert response.status_code == 200
    assert json.loads(response.data)["status"] == "draft"
