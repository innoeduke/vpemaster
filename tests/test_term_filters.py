
import pytest
from datetime import date, timedelta
from app.utils import get_terms, get_date_ranges_for_terms
from app.models import Meeting, SessionLog, Contact, MeetingRole, Roster, User, AuthRole, Permission
from app import db

def test_get_date_ranges_for_terms(app):
    with app.app_context():
        terms = get_terms()
        from datetime import datetime
        
        # helper
        def to_date(d_str):
            return datetime.strptime(d_str, '%Y-%m-%d').date()
        
        # Assume we pick the first two terms
        if len(terms) >= 2:
            term1 = terms[0]
            term2 = terms[1]
            
            selected_ids = [term1['id'], term2['id']]
            ranges = get_date_ranges_for_terms(selected_ids, terms)
            
            assert len(ranges) == 2
            assert (to_date(term1['start']), to_date(term1['end'])) in ranges
            assert (to_date(term2['start']), to_date(term2['end'])) in ranges

@pytest.fixture
def auth_client(client, app, default_club, default_contact):
    """Fixture to provide an authenticated client"""
    from app.models import UserClub
    
    with app.app_context():
        # Create Admin Role first
        role = AuthRole.query.filter_by(name='Admin').first()
        if not role:
            role = AuthRole(name='Admin', level=100)
            db.session.add(role)
            db.session.commit()

        # Create User if not exists
        user = User.query.filter_by(username='testadmin').first()
        if not user:
            user = User(username='testadmin', email='admin@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            
        # Ensure user is linked to contact via UserClub
        uc = UserClub.query.filter_by(user_id=user.id, club_id=default_club.id).first()
        if not uc:
            uc = UserClub(
                user_id=user.id, 
                club_id=default_club.id, 
                contact_id=default_contact.id,
                club_role_level=role.level 
            )
            db.session.add(uc)
        else:
             uc.contact_id = default_contact.id
             uc.club_role_level = role.level
             
        db.session.commit()
        
        # Give permissions
        perms = [Permissions.CONTACT_BOOK_VIEW, Permissions.SPEECH_LOGS_VIEW_ALL]
        for p_name in perms:
            perm = Permission.query.filter_by(name=p_name).first()
            if not perm:
                perm = Permission(name=p_name)
                db.session.add(perm)
            if perm not in role.permissions:
                role.permissions.append(perm)
                
        db.session.commit()
        
    # Login
    client.post('/login', data=dict(username='testadmin', password='password'), follow_redirects=True)
    return client

from app.auth.permissions import Permissions

def test_contacts_term_filter_integration(auth_client, app):
    with app.app_context():
        # Setup data
        terms = get_terms()
        if len(terms) < 3:
            pytest.skip("Not enough terms generated to test filter")
            
        t1 = terms[1] 
        t2 = terms[2]
        
        from app.club_context import get_current_club_id
        club_id = get_current_club_id() or 1
        
        from datetime import datetime
        
        # Create meetings in these terms
        # Convert string dates to python date objects
        d1 = datetime.strptime(t1['start'], '%Y-%m-%d').date()
        d2 = datetime.strptime(t2['start'], '%Y-%m-%d').date()
        
        m1 = Meeting(Meeting_Date=d1, Meeting_Number=9001, club_id=club_id)
        m2 = Meeting(Meeting_Date=d2, Meeting_Number=9002, club_id=club_id)
        db.session.add(m1)
        db.session.add(m2)
        
        # Create a test contact
        c = Contact(Name="Filter Tester")
        db.session.add(c)
        db.session.commit()
        
        # Link contact to club (needed for ContactClub join in route)
        from app.models import ContactClub
        cc = ContactClub(contact_id=c.id, club_id=club_id)
        db.session.add(cc)
        
        # Add Roster attendance
        r1 = Roster(contact_id=c.id, meeting_id=m1.id)
        r2 = Roster(contact_id=c.id, meeting_id=m2.id)
        db.session.add(r1)
        db.session.add(r2)
        db.session.commit()
        
        import re
        
        def get_attendance_count(response_data):
            import json
            data = json.loads(response_data)
            # Find the contact we created
            contact_entry = next((item for item in data if item['id'] == c.id), None)
            return contact_entry['attendance_count'] if contact_entry else 0
        
        # Add Role participation (OwnerMeetingRoles)
        from app.models import OwnerMeetingRoles, MeetingRole
        
        # Ensure a standard role exists (or create one)
        role_tm = MeetingRole.query.filter_by(name="Toastmaster").first()
        if not role_tm:
            role_tm = MeetingRole(name="Toastmaster", type="standard", needs_approval=False, has_single_owner=True, is_member_only=False)
            db.session.add(role_tm)
            db.session.commit()
            
        # Create OM Roles
        omr1 = OwnerMeetingRoles(meeting_id=m1.id, role_id=role_tm.id, contact_id=c.id)
        omr2 = OwnerMeetingRoles(meeting_id=m2.id, role_id=role_tm.id, contact_id=c.id)
        db.session.add(omr1)
        db.session.add(omr2)
        db.session.commit()
        
        # Helper for roles
        def get_role_count(response_data):
            import json
            data = json.loads(response_data)
            # Find the contact we created
            contact_entry = next((item for item in data if item['id'] == c.id), None)
            return contact_entry['role_count'] if contact_entry else 0

        # Test 1: Query Term 1 -> Expect 1 attendance match (r1)
        resp = auth_client.get(f'/api/contacts/all?term={t1["id"]}')
        assert resp.status_code == 200
        count_t1 = get_attendance_count(resp.data)
        assert count_t1 == 1, f"Expected 1 attendance for T1, got {count_t1}"
        role_count_t1 = get_role_count(resp.data)
        assert role_count_t1 == 1, f"Expected 1 role for T1, got {role_count_t1}"

        # Test 2 details: Query Term 2 -> Expect 1 attendance match (r2)
        resp_t2 = auth_client.get(f'/api/contacts/all?term={t2["id"]}')
        assert resp_t2.status_code == 200
        count_t2 = get_attendance_count(resp_t2.data)
        assert count_t2 == 1, f"Expected 1 attendance for T2, got {count_t2}"
        
        # Test 3: Multi-select (T1 + T2) -> Expect 2 attendance matches
        resp_multi = auth_client.get(f'/api/contacts/all?term={t1["id"]}&term={t2["id"]}')
        assert resp_multi.status_code == 200
        count_multi = get_attendance_count(resp_multi.data)
        assert count_multi == 2, f"Expected 2 attendance for T1+T2, got {count_multi}"
        
        role_count_multi = get_role_count(resp_multi.data)
        assert role_count_multi == 2, f"Expected 2 roles for T1+T2, got {role_count_multi}"

        # Test 4: Select All Visual State
        # Get all term IDs
        all_term_ids = [t['id'] for t in terms]
        # Construct query string
        query_pairs = [f'term={tid}' for tid in all_term_ids]
        query_string = '&'.join(query_pairs)
        
        resp3 = auth_client.get(f'/contacts?{query_string}')
        assert resp3.status_code == 200
        # Check if the "Select / Deselect All" checkbox has the 'checked' attribute
        assert b'checked' in resp3.data
        assert b'id="term-select-all"' in resp3.data

        # Cleanup (keep the rest)
        db.session.delete(omr1)
        db.session.delete(omr2)
        db.session.delete(r2)
        db.session.delete(cc)
        db.session.delete(c)
        db.session.delete(m1)
        db.session.delete(m2)
        db.session.commit()

def test_project_view_term_filter_integration(auth_client, app):
    # Just check it accepts the params and renders
    resp = auth_client.get('/speech_logs/projects')
    assert resp.status_code == 200
    assert b'term' in resp.data or b'Term' in resp.data
