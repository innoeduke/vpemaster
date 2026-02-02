"""Tests for multi-club access control decorator."""
import pytest
from flask import session
from app.models import db, Club, Contact, ContactClub, User, AuthRole, Permission, ExComm, UserClub, MeetingRole, ExcommOfficer


@pytest.fixture(scope='session', autouse=True)
def cleanup_test_data(app):
    """Clean up any leftover test data before and after all tests."""
    def cleanup():
        with app.app_context():
            # Clean up in proper order to respect foreign keys
            # First, get contact IDs to clean
            test_contacts = Contact.query.filter(Contact.Name.like('Test %')).all()
            test_contact_ids = [c.id for c in test_contacts]
            
            # Delete in proper order (children first, then parents)
            # 0. Set current_excomm_id to NULL for test clubs FIRST (before deleting ExComm)
            test_clubs = Club.query.filter(Club.club_no.like('TEST_%')).all()
            for club in test_clubs:
                club.current_excomm_id = None
            db.session.flush()
            
            # 1. Delete ExComm records that reference test contacts
            if test_contact_ids:
                # Note: Cascade delete on ExcommOfficer should handle the association table
                # We just need to find ExComms that might be related via legacy means or direct cleanup
                pass
            
            # 2. Delete all records that reference test contacts
            if test_contact_ids:
                from app.models import SessionLog, UserClub, Waitlist, Vote, Roster, Achievement, RosterRole
                # SessionLog cleanup handled by cascaded delete or manual cleanup 
                # (Standard delete(synchronize_session=False) doesn't work well with M2M)
                for log in SessionLog.query.all():
                    if any(o.id in test_contact_ids for o in log.owners):
                        db.session.delete(log)
                db.session.flush()
                Waitlist.query.filter(Waitlist.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                Vote.query.filter(Vote.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                
                # Delete RosterRole before Roster
                roster_ids = [r.id for r in Roster.query.filter(Roster.contact_id.in_(test_contact_ids)).all()]
                if roster_ids:
                    RosterRole.query.filter(RosterRole.roster_id.in_(roster_ids)).delete(synchronize_session=False)
                Roster.query.filter(Roster.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                
                Achievement.query.filter(Achievement.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                UserClub.query.filter(UserClub.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                ContactClub.query.filter(ContactClub.contact_id.in_(test_contact_ids)).delete(synchronize_session=False)
                db.session.commit()
            
            # 3. Delete Users (they reference Contacts)
            User.query.filter(User.username.like('test_%')).delete(synchronize_session=False)
            db.session.commit()
            
            # 4. Set Mentor_ID to NULL for contacts we're about to delete
            # to avoid self-referential foreign key constraint failures
            Contact.query.filter(Contact.Name.like('Test %')).update({Contact.Mentor_ID: None}, synchronize_session=False)
            db.session.flush()

            # 5. Delete Contacts
            Contact.query.filter(Contact.Name.like('Test %')).delete()
            
            # 6. Delete Clubs
            Club.query.filter(Club.club_no.like('TEST_%')).delete()
            
            db.session.commit()
    
    cleanup()  # Clean before tests
    yield
    cleanup()  # Clean after tests


def test_sysadmin_access_any_club(app, client):
    """Test that a SysAdmin can access any club."""
    with app.app_context():
        # Setup - Create clubs
        club1 = Club(club_no='TEST_C1', club_name='Test Club 1')
        club2 = Club(club_no='TEST_C2', club_name='Test Club 2')
        db.session.add_all([club1, club2])
        db.session.flush()
        
        # Setup - Create SysAdmin user
        admin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        if not admin_role:
            admin_role = AuthRole(name='SysAdmin', level=8)
            db.session.add(admin_role)
            db.session.flush()
        
        user = User(username='test_sysadmin', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        user.add_role(admin_role)
        # Grant SysAdmin role in user_clubs as well
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, club_role_level=admin_role.level))
        db.session.commit()
        
        # Test access to club1
        with app.test_request_context():
            session['current_club_id'] = club1.id
            
            from flask_login import login_user
            from app.club_context import authorized_club_required
            login_user(user)
            
            @authorized_club_required
            def dummy_view():
                return "Success"
            
            assert dummy_view() == "Success"
        
        # Test access to club2 (no membership)
        with app.test_request_context():
            session['current_club_id'] = club2.id
            login_user(user)
            
            @authorized_club_required
            def dummy_view2():
                return "Success"
            
            assert dummy_view2() == "Success"


def test_clubadmin_access_owned_club(app, client):
    """Test that a ClubAdmin can access clubs where they are an officer."""
    with app.app_context():
        # Setup - Create club
        club1 = Club(club_no='TEST_C3', club_name='Test Club 3')
        db.session.add(club1)
        db.session.flush()
        
        # Setup - Create ClubAdmin user
        clubadmin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not clubadmin_role:
            clubadmin_role = AuthRole(name='ClubAdmin', level=4)
            db.session.add(clubadmin_role)
            db.session.flush()
        
        contact = Contact(Name='Test ClubAdmin', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(username='test_clubadmin', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        user.add_role(clubadmin_role)
        # Grant ClubAdmin role for club1 in user_clubs
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, club_role_level=clubadmin_role.level, contact_id=contact.id))
        
        # Create ExComm for club1 with this user as VPE
        excomm = ExComm(club_id=club1.id, excomm_term='TEST_26H1')
        db.session.add(excomm)
        db.session.flush()
        
        # Create VPE role if it doesn't exist
        vpe_role = MeetingRole.query.filter_by(name='VPE', club_id=None).first()
        if not vpe_role:
            vpe_role = MeetingRole(name='VPE', type='Officer', needs_approval=False, has_single_owner=True)
            db.session.add(vpe_role)
            db.session.flush()
            
        # Assign VPE role via ExcommOfficer
        officer = ExcommOfficer(excomm_id=excomm.id, contact_id=contact.id, meeting_role_id=vpe_role.id)
        db.session.add(officer)
        
        club1.current_excomm_id = excomm.id
        db.session.commit()
        
        # Test access to club1 (where they are VPE)
        with app.test_request_context():
            session['current_club_id'] = club1.id
            
            from flask_login import login_user
            from app.club_context import authorized_club_required
            login_user(user)
            
            @authorized_club_required
            def dummy_view():
                return "Success"
            
            assert dummy_view() == "Success"


def test_clubadmin_denied_non_owned_club(app, client):
    """Test that a ClubAdmin is denied access to clubs where they are not an officer."""
    from werkzeug.exceptions import Forbidden
    
    with app.app_context():
        # Setup - Create two clubs
        club1 = Club(club_no='TEST_C4', club_name='Test Club 4')
        club2 = Club(club_no='TEST_C5', club_name='Test Club 5')
        db.session.add_all([club1, club2])
        db.session.flush()
        
        # Setup - Create ClubAdmin user (officer in club1 only)
        clubadmin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not clubadmin_role:
            clubadmin_role = AuthRole(name='ClubAdmin', level=4)
            db.session.add(clubadmin_role)
            db.session.flush()
        
        contact = Contact(Name='Test ClubAdmin 2', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(username='test_clubadmin2', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        user.add_role(clubadmin_role)
        # Grant ClubAdmin role for club1 in user_clubs
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, club_role_level=clubadmin_role.level, contact_id=contact.id))
        
        # Create ExComm for club1 only
        excomm = ExComm(club_id=club1.id, excomm_term='TEST_26H1')
        db.session.add(excomm)
        db.session.flush()
        
        # Create President role if it doesn't exist
        pres_role = MeetingRole.query.filter_by(name='President', club_id=None).first()
        if not pres_role:
            pres_role = MeetingRole(name='President', type='Officer', needs_approval=False, has_single_owner=True)
            db.session.add(pres_role)
            db.session.flush()
            
        # Assign President role via ExcommOfficer
        officer = ExcommOfficer(excomm_id=excomm.id, contact_id=contact.id, meeting_role_id=pres_role.id)
        db.session.add(officer)

        club1.current_excomm_id = excomm.id
        db.session.commit()
        
        # Test access to club2 (where they are NOT an officer and have no membership)
        with app.test_request_context():
            session['current_club_id'] = club2.id
            
            from flask_login import login_user
            from app.club_context import authorized_club_required
            login_user(user)
            
            @authorized_club_required
            def dummy_view():
                return "Success"
            
            # The system should automatically switch context to a valid club (club1)
            # instead of raising Forbidden
            result = dummy_view()
            assert result == "Success"
            
            # Verify context was switched to club1 (where they are officer)
            assert session['current_club_id'] == club1.id


def test_regular_user_access_authorized_club(app, client):
    """Test that a regular user can access their authorized club."""
    with app.app_context():
        # Setup - Create club
        club1 = Club(club_no='TEST_C6', club_name='Test Club 6')
        db.session.add(club1)
        db.session.flush()
        
        # Setup - Create regular user
        user_role = AuthRole.query.filter_by(name='User').first()
        if not user_role:
            user_role = AuthRole(name='User', level=1)
            db.session.add(user_role)
            db.session.flush()
        
        contact = Contact(Name='Test Regular User', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(username='test_regular', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        user.add_role(user_role)
        
        # Add membership to club1
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, contact_id=contact.id, club_role_level=user_role.level))
        membership = ContactClub(
            contact_id=contact.id,
            club_id=club1.id
        )
        db.session.add(membership)
        db.session.commit()
        
        # Test access to club1 (where they have membership)
        with app.test_request_context():
            session['current_club_id'] = club1.id
            
            from flask_login import login_user
            from app.club_context import authorized_club_required
            login_user(user)
            
            @authorized_club_required
            def dummy_view():
                return "Success"
            
            assert dummy_view() == "Success"


def test_regular_user_denied_unauthorized_club(app, client):
    """Test that a regular user is denied access to clubs they don't belong to."""
    from werkzeug.exceptions import Forbidden
    
    with app.app_context():
        # Setup - Create two clubs
        club1 = Club(club_no='TEST_C7', club_name='Test Club 7')
        club2 = Club(club_no='TEST_C8', club_name='Test Club 8')
        db.session.add_all([club1, club2])
        db.session.flush()
        
        # Setup - Create regular user (member of club1 only)
        user_role = AuthRole.query.filter_by(name='User').first()
        if not user_role:
            user_role = AuthRole(name='User', level=1)
            db.session.add(user_role)
            db.session.flush()
        
        contact = Contact(Name='Test Regular User 2', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(username='test_regular2', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        user.add_role(user_role)
        
        # Add membership to club1 only
        db.session.add(UserClub(user_id=user.id, club_id=club1.id, contact_id=contact.id, club_role_level=user_role.level))
        membership = ContactClub(
            contact_id=contact.id,
            club_id=club1.id
        )
        db.session.add(membership)
        db.session.commit()
        
        # Test access to club2 (where they have NO membership)
        with app.test_request_context():
            session['current_club_id'] = club2.id
            
            from flask_login import login_user
            from app.club_context import authorized_club_required
            login_user(user)
            
            @authorized_club_required
            def dummy_view():
                return "Success"
            
            # The system should automatically switch context to a valid club (club1)
            # instead of raising Forbidden
            result = dummy_view()
            assert result == "Success"
            
            # Verify context was switched to club1 (where they are member)
            assert session['current_club_id'] == club1.id
