"""Tests for Club and ExComm models."""
import pytest
from app.models import Club, ExComm, Contact, MeetingRole, ExcommOfficer
from app import db


def test_club_model_exists(app, default_club):
    """Test that Club model can be queried."""
    with app.app_context():
        club = Club.query.first()
        assert club is not None, "Club should exist in database"


def test_club_model_fields(app, default_club):
    """Test that Club model has all required fields."""
    with app.app_context():
        club = Club.query.first()
        assert club is not None
        
        # Test all fields are accessible
        assert club.id is not None
        assert club.club_no is not None
        assert club.club_name is not None
        assert hasattr(club, 'short_name')
        assert hasattr(club, 'district')
        assert hasattr(club, 'division')
        assert hasattr(club, 'area')
        assert hasattr(club, 'club_address')
        assert hasattr(club, 'meeting_date')
        assert hasattr(club, 'meeting_time')
        assert hasattr(club, 'contact_phone_number')
        assert hasattr(club, 'founded_date')
        assert hasattr(club, 'current_excomm_id')


def test_club_to_dict(app, default_club):
    """Test Club model to_dict method."""
    with app.app_context():
        club = Club.query.first()
        assert club is not None
        
        club_dict = club.to_dict()
        assert isinstance(club_dict, dict)
        assert 'id' in club_dict
        assert 'club_no' in club_dict
        assert 'club_name' in club_dict
        assert 'short_name' in club_dict
        assert 'founded_date' in club_dict


def test_excomm_model_exists(app, default_excomm):
    """Test that ExComm model can be queried."""
    with app.app_context():
        excomm = ExComm.query.first()
        assert excomm is not None, "ExComm should exist in database"


def test_excomm_model_fields(app, default_excomm):
    """Test that ExComm model has all required fields."""
    with app.app_context():
        excomm = ExComm.query.first()
        assert excomm is not None
        
        # Test all fields are accessible
        assert excomm.id is not None
        assert excomm.club_id is not None
        assert excomm.excomm_term is not None
        assert hasattr(excomm, 'excomm_name')
        
        # New model uses association table
        assert hasattr(excomm, 'officers')
        # Legacy fields should be gone
        assert not hasattr(excomm, 'president_id')
        assert not hasattr(excomm, 'vpe_id')


def test_excomm_get_officers(app, default_excomm):
    """Test ExComm get_officers method."""
    with app.app_context():
        excomm = ExComm.query.first()
        assert excomm is not None
        
        # Setup: Create officers
        roles = ['President', 'VPE', 'VPM', 'VPPR', 'Secretary', 'Treasurer', 'SAA']
        for role_name in roles:
            role = MeetingRole.query.filter_by(name=role_name, club_id=None).first()
            if not role:
                role = MeetingRole(name=role_name, type='Officer', needs_approval=False, has_single_owner=True)
                db.session.add(role)
                db.session.flush()
            
            # Create dummy contact
            contact = Contact(Name=f'{role_name} Test', Type='Member')
            db.session.add(contact)
            db.session.flush()
            
            # Link
            if not ExcommOfficer.query.filter_by(excomm_id=excomm.id, meeting_role_id=role.id).first():
                officer = ExcommOfficer(excomm_id=excomm.id, contact_id=contact.id, meeting_role_id=role.id)
                db.session.add(officer)
        db.session.commit()
        
        officers = excomm.get_officers()
        assert isinstance(officers, dict)
        # Check specific roles exist in the returned dictionary
        assert 'President' in officers
        assert 'VPE' in officers


def test_excomm_get_officer_by_role(app, default_excomm):
    """Test ExComm get_officer_by_role method."""
    with app.app_context():
        excomm = ExComm.query.first()
        assert excomm is not None
        
        # Test getting an officer by role
        # Test getting an officer by role
        # We know President was added in previous test or can be added here
        # But fixtures might reset db per function? Yes, clean_db uses function scope.
        
        # So we need to add at least one officer here
        role = MeetingRole.query.filter_by(name='President').first()
        if not role:
            role = MeetingRole(name='President', type='Officer', needs_approval=False, has_single_owner=True)
            db.session.add(role)
            db.session.flush()
            
        contact = Contact(Name='President Test', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        if not ExcommOfficer.query.filter_by(excomm_id=excomm.id, meeting_role_id=role.id).first():
            officer = ExcommOfficer(excomm_id=excomm.id, contact_id=contact.id, meeting_role_id=role.id)
            db.session.add(officer)
        db.session.commit()

        president = excomm.get_officer_by_role('President')
        assert isinstance(president, Contact)
        assert president.Name == 'President Test'
        
        # Test case insensitivity
        president_lower = excomm.get_officer_by_role('president')
        assert isinstance(president_lower, Contact)


def test_club_excomm_relationship(app, default_club, default_excomm):
    """Test relationship between Club and ExComm."""
    with app.app_context():
        club = Club.query.first()
        assert club is not None
        
        # Test current_excomm relationship
        if club.current_excomm_id:
            assert club.current_excomm is not None
            assert isinstance(club.current_excomm, ExComm)
            assert club.current_excomm.club_id == club.id
