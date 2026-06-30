"""Tests for redesigned Excomm features, sorting, and assistant officers."""
import pytest
from app.models import Club, ExComm, Contact, MeetingRole, ExcommOfficer, User, AuthRole, UserClub, Permission, RolePermission
from app import db
from datetime import date


def test_officer_roles_sorting(app, default_club):
    """Test that officer roles are sorted President, VPE, VPM, VPPR, Secretary, Treasurer, SAA, IPP."""
    with app.app_context():
        # Clean all local roles first to avoid collisions
        roles = MeetingRole.get_all_for_club(default_club.id)
        officer_roles = [r for r in roles if r.type == 'officer']
        
        # If standard roles are not created, seed them
        if not officer_roles:
            standard_officers = ['Immediate Past President', 'SAA', 'Treasurer', 'Secretary', 'VPPR', 'VPM', 'VPE', 'President']
            for name in standard_officers:
                role = MeetingRole(name=name, type='officer', club_id=default_club.id, needs_approval=False, has_single_owner=True)
                db.session.add(role)
            db.session.commit()
            roles = MeetingRole.get_all_for_club(default_club.id)
            officer_roles = [r for r in roles if r.type == 'officer']
            
        role_order = {
            'President': 0,
            'VPE': 1,
            'VPM': 2,
            'VPPR': 3,
            'Secretary': 4,
            'Treasurer': 5,
            'SAA': 6,
            'Immediate Past President': 7
        }
        officer_roles.sort(key=lambda r: role_order.get(r.name, 999))
        
        sorted_names = [r.name for r in officer_roles if r.name in role_order]
        expected_names = ['President', 'VPE', 'VPM', 'VPPR', 'Secretary', 'Treasurer', 'SAA', 'Immediate Past President']
        
        # Verify order
        assert sorted_names == expected_names


def test_excomm_add_and_update_with_assistants(app, default_club):
    """Test adding and updating an Excomm term with primary and assistant officers."""
    with app.app_context():
        # Get/create roles
        vpe_role = MeetingRole.query.filter_by(name='VPE').first()
        if not vpe_role:
            vpe_role = MeetingRole(name='VPE', type='officer', club_id=default_club.id, needs_approval=False, has_single_owner=True)
            db.session.add(vpe_role)
            db.session.commit()
            
        # Create contacts
        c_primary = Contact(Name='Primary VPE', Type='Member')
        c_asst1 = Contact(Name='Assistant VPE One', Type='Member')
        c_asst2 = Contact(Name='Assistant VPE Two', Type='Member')
        db.session.add_all([c_primary, c_asst1, c_asst2])
        db.session.commit()
        
        # Create excomm
        excomm = ExComm(
            club_id=default_club.id,
            excomm_term='26H1',
            excomm_name='Test Excomm Team',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30)
        )
        db.session.add(excomm)
        db.session.flush()
        
        # Add primary officer
        o_primary = ExcommOfficer(
            excomm_id=excomm.id,
            contact_id=c_primary.id,
            meeting_role_id=vpe_role.id,
            is_assistant=False
        )
        db.session.add(o_primary)
        
        # Add assistant officers
        o_asst1 = ExcommOfficer(
            excomm_id=excomm.id,
            contact_id=c_asst1.id,
            meeting_role_id=vpe_role.id,
            is_assistant=True
        )
        o_asst2 = ExcommOfficer(
            excomm_id=excomm.id,
            contact_id=c_asst2.id,
            meeting_role_id=vpe_role.id,
            is_assistant=True
        )
        db.session.add_all([o_asst1, o_asst2])
        db.session.commit()
        
        # Test get_officers() - should only return primary
        primary_officers = excomm.get_officers()
        assert len(primary_officers) == 1
        assert primary_officers['VPE'].Name == 'Primary VPE'
        
        # Test get_officers_json() - should return all three
        officers_json = excomm.get_officers_json()
        assert len(officers_json) == 3
        
        primary_link = next(x for x in officers_json if not x['is_assistant'])
        assert primary_link['contact_name'] == 'Primary VPE'
        
        assistant_links = [x for x in officers_json if x['is_assistant']]
        assert len(assistant_links) == 2
        assert {x['contact_name'] for x in assistant_links} == {'Assistant VPE One', 'Assistant VPE Two'}
        
        # Verify unique constraint `uq_excomm_contact_role` prevents duplicate link
        with pytest.raises(Exception):
            dup_link = ExcommOfficer(
                excomm_id=excomm.id,
                contact_id=c_primary.id,
                meeting_role_id=vpe_role.id,
                is_assistant=True # duplicate contact for same role/excomm
            )
            db.session.add(dup_link)
            db.session.commit()
        db.session.rollback()


def test_excomm_endpoints(client, app, default_club):
    """Test HTTP endpoints for split excomm term and individual officer management."""
    # Seed mock user
    with app.app_context():
        user = User.query.filter_by(username='sysadmin').first()
        if not user:
            user = User(username='sysadmin', email='admin@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        uid = user.id
            
    # Mock logged in session via client
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['_user_id'] = str(uid)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # 1. Add Excomm Term
    res = client.post('/settings/excomm/add', json={
        'term': '27H1',
        'name': 'Split Modal Team',
        'start_date': '2027-01-01',
        'end_date': '2027-06-30'
    })
    assert res.status_code == 200
    assert res.json['success'] is True

    # Verify term was created
    with app.app_context():
        excomm = ExComm.query.filter_by(excomm_term='27H1').first()
        assert excomm is not None
        assert excomm.excomm_name == 'Split Modal Team'
        
        vpe_role = MeetingRole.query.filter_by(name='VPE').first()
        if not vpe_role:
            vpe_role = MeetingRole(name='VPE', type='officer', club_id=default_club.id, needs_approval=False, has_single_owner=True)
            db.session.add(vpe_role)
            db.session.commit()
            
        c_officer1 = Contact(Name='API Officer One', Type='Member')
        c_officer2 = Contact(Name='API Officer Two', Type='Member')
        db.session.add_all([c_officer1, c_officer2])
        db.session.commit()
        
        excomm_id = excomm.id
        role_id = vpe_role.id
        c1_id = c_officer1.id
        c2_id = c_officer2.id

    # 2. Add Primary Officer via API
    res = client.post('/settings/excomm/officer/add', json={
        'excomm_id': excomm_id,
        'role_id': role_id,
        'contact_id': c1_id,
        'is_assistant': False
    })
    assert res.status_code == 200
    assert res.json['success'] is True

    # 3. Add Duplicate Primary Officer (should fail validation)
    res = client.post('/settings/excomm/officer/add', json={
        'excomm_id': excomm_id,
        'role_id': role_id,
        'contact_id': c2_id,
        'is_assistant': False
    })
    assert res.status_code == 400
    assert "already has a primary officer" in res.json['message']

    # 4. Add Assistant Officer (should succeed)
    res = client.post('/settings/excomm/officer/add', json={
        'excomm_id': excomm_id,
        'role_id': role_id,
        'contact_id': c2_id,
        'is_assistant': True
    })
    assert res.status_code == 200
    assert res.json['success'] is True

    # Retrieve officer assignments to test edit and delete
    with app.app_context():
        officers = ExcommOfficer.query.filter_by(excomm_id=excomm_id).all()
        assert len(officers) == 2
        primary_link = next(o for o in officers if not o.is_assistant)
        asst_link = next(o for o in officers if o.is_assistant)
        primary_link_id = primary_link.id
        asst_link_id = asst_link.id

    # 5. Update Officer
    res = client.post('/settings/excomm/officer/update', json={
        'id': asst_link_id,
        'role_id': role_id,
        'contact_id': c2_id,
        'is_assistant': False # try to change assistant to primary
    })
    # Since there's already a primary officer (c1), this should fail
    assert res.status_code == 400
    assert "already has a primary officer" in res.json['message']

    # 6. Delete Officer Assignment
    res = client.post(f'/settings/excomm/officer/delete/{asst_link_id}')
    assert res.status_code == 200
    assert res.json['success'] is True

    with app.app_context():
        remain_officers = ExcommOfficer.query.filter_by(excomm_id=excomm_id).all()
        assert len(remain_officers) == 1
        assert remain_officers[0].id == primary_link_id


def test_excomm_route_access(client, app, default_club):
    """Test that /excomm page is accessible when logged in."""
    with app.app_context():
        user = User.query.filter_by(username='sysadmin').first()
        if not user:
            user = User(username='sysadmin', email='admin@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
        uid = user.id
            
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['_user_id'] = str(uid)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True
        
    response = client.get('/excomm')
    assert response.status_code == 200


def test_excomm_club_manage_permission(client, app, default_club):
    """Test that club_manage permission controls editing excomm records."""
    with app.app_context():
        # Clean up any existing member test user
        old_user = User.query.filter_by(username='test_member').first()
        if old_user:
            UserClub.query.filter_by(user_id=old_user.id).delete()
            db.session.delete(old_user)
            db.session.commit()

        # Seed Member role if not present
        member_role = AuthRole.query.filter_by(name='Member').first()
        if not member_role:
            member_role = AuthRole(name='Member', level=1)
            db.session.add(member_role)
            db.session.commit()

        # Seed ROSTER_VIEW permission if not present
        roster_view_perm = Permission.query.filter_by(name='ROSTER_VIEW').first()
        if not roster_view_perm:
            roster_view_perm = Permission(name='ROSTER_VIEW', category='roster')
            db.session.add(roster_view_perm)
            db.session.commit()

        # Link ROSTER_VIEW to Member role for the club
        rp = RolePermission.query.filter_by(role_id=member_role.id, permission_id=roster_view_perm.id, club_id=default_club.id).first()
        if not rp:
            rp = RolePermission(role_id=member_role.id, permission_id=roster_view_perm.id, club_id=default_club.id)
            db.session.add(rp)
            db.session.commit()

        # Create user
        user = User(username='test_member', email='member@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        uc = UserClub(user_id=user.id, club_id=default_club.id, auth_role_id=member_role.id)
        db.session.add(uc)
        db.session.commit()
        
        uid = user.id

    # Log in as test_member
    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['_user_id'] = str(uid)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # 1. Member has ROSTER_VIEW, so they should be able to view /excomm (status code 200)
    response = client.get('/excomm')
    assert response.status_code == 200

    # 2. But Member does NOT have CLUB_MANAGE, so attempting to add excomm should return 403 Forbidden
    res = client.post('/settings/excomm/add', json={
        'term': '27H1',
        'name': 'Test Forbidden Team',
        'start_date': '2027-01-01',
        'end_date': '2027-06-30'
    })
    assert res.status_code == 403


