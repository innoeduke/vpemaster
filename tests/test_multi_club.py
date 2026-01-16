"""Tests for multi-club support database schema and relationships."""
import pytest
from app.models import db, Club, Contact, ContactClub, Meeting


class TestClubTable:
    """Tests for clubs table and Club model."""
    
    def test_clubs_table_exists(self, app):
        """Test that clubs table exists and has data."""
        with app.app_context():
            clubs = Club.query.all()
            assert len(clubs) > 0, "At least one club should exist in database"
    
    def test_club_has_required_fields(self, app):
        """Test that Club model has all required fields."""
        with app.app_context():
            club = Club.query.first()
            assert club is not None
            assert club.id is not None
            assert club.club_no is not None
            assert club.club_name is not None
            assert hasattr(club, 'district')
            assert hasattr(club, 'division')
            assert hasattr(club, 'area')
            assert hasattr(club, 'club_address')
            assert hasattr(club, 'meeting_date')
            assert hasattr(club, 'meeting_time')
            assert hasattr(club, 'contact_phone_number')


class TestContactClubJunctionTable:
    """Tests for contact_clubs junction table."""
    
    def test_contact_clubs_table_exists(self, app):
        """Test that contact_clubs junction table exists and has data."""
        with app.app_context():
            contact_clubs = ContactClub.query.all()
            assert len(contact_clubs) > 0, "Contact-club associations should exist"
    
    def test_contact_club_has_required_fields(self, app):
        """Test that ContactClub model has all required fields."""
        with app.app_context():
            cc = ContactClub.query.first()
            assert cc is not None
            assert cc.id is not None
            assert cc.contact_id is not None
            assert cc.club_id is not None
            assert hasattr(cc, 'membership_type')
            assert hasattr(cc, 'joined_date')
            assert hasattr(cc, 'is_primary')
            assert isinstance(cc.is_primary, bool)
    
    def test_all_contacts_have_primary_club(self, app):
        """Test that all contacts with club associations have a primary club."""
        with app.app_context():
            # Get all unique contacts in contact_clubs
            contact_ids = db.session.query(ContactClub.contact_id).distinct().all()
            contact_ids = [cid[0] for cid in contact_ids]
            
            for contact_id in contact_ids:
                primary_count = ContactClub.query.filter_by(
                    contact_id=contact_id, 
                    is_primary=True
                ).count()
                assert primary_count >= 1, f"Contact {contact_id} should have at least one primary club"
    
    def test_contact_club_unique_constraint(self, app):
        """Test that contact-club combination is unique."""
        with app.app_context():
            # Get a sample contact-club association
            cc = ContactClub.query.first()
            assert cc is not None
            
            # Count associations for this contact-club pair
            count = ContactClub.query.filter_by(
                contact_id=cc.contact_id,
                club_id=cc.club_id
            ).count()
            
            assert count == 1, "Contact-club combination should be unique"


class TestMeetingClubRelationship:
    """Tests for Meeting-Club relationship."""
    
    def test_all_meetings_have_club_id(self, app):
        """Test that all meetings have club_id assigned."""
        with app.app_context():
            total_meetings = Meeting.query.count()
            
            if total_meetings > 0:
                meetings_with_club = Meeting.query.filter(
                    Meeting.club_id.isnot(None)
                ).count()
                
                assert meetings_with_club == total_meetings, \
                    f"{total_meetings - meetings_with_club} meetings missing club_id"
    
    def test_meeting_club_relationship(self, app):
        """Test that Meeting.club relationship works."""
        with app.app_context():
            meeting = Meeting.query.first()
            
            if meeting:
                assert hasattr(meeting, 'club'), "Meeting should have club attribute"
                assert meeting.club is not None, "Meeting.club should not be None"
                assert isinstance(meeting.club, Club), "Meeting.club should be a Club instance"
                assert meeting.club.id == meeting.club_id, "Club relationship should match club_id"
    
    def test_meeting_club_id_foreign_key(self, app):
        """Test that meeting.club_id references valid club."""
        with app.app_context():
            meetings = Meeting.query.all()
            
            for meeting in meetings:
                club = Club.query.get(meeting.club_id)
                assert club is not None, \
                    f"Meeting {meeting.id} references non-existent club {meeting.club_id}"


class TestContactClubMethods:
    """Tests for Contact model club-related methods."""
    
    def test_get_primary_club(self, app):
        """Test Contact.get_primary_club() method."""
        with app.app_context():
            # Get a contact with club associations
            cc = ContactClub.query.filter_by(is_primary=True).first()
            assert cc is not None, "Should have at least one primary club association"
            
            contact = Contact.query.get(cc.contact_id)
            assert contact is not None
            
            primary_club = contact.get_primary_club()
            assert primary_club is not None, "get_primary_club() should return a club"
            assert isinstance(primary_club, Club), "Should return a Club instance"
            assert primary_club.id == cc.club_id, "Should return the correct primary club"
    
    def test_get_clubs(self, app):
        """Test Contact.get_clubs() method."""
        with app.app_context():
            # Get a contact with club associations
            cc = ContactClub.query.first()
            assert cc is not None
            
            contact = Contact.query.get(cc.contact_id)
            assert contact is not None
            
            clubs = contact.get_clubs()
            assert isinstance(clubs, list), "get_clubs() should return a list"
            assert len(clubs) > 0, "Contact should belong to at least one club"
            assert all(isinstance(club, Club) for club in clubs), \
                "All items should be Club instances"
    
    def test_get_club_membership(self, app):
        """Test Contact.get_club_membership() method."""
        with app.app_context():
            # Get a contact with club associations
            cc = ContactClub.query.first()
            assert cc is not None
            
            contact = Contact.query.get(cc.contact_id)
            assert contact is not None
            
            membership = contact.get_club_membership(cc.club_id)
            assert membership is not None, "get_club_membership() should return membership"
            assert isinstance(membership, ContactClub), "Should return ContactClub instance"
            assert membership.contact_id == contact.id
            assert membership.club_id == cc.club_id
    
    def test_get_club_membership_nonexistent(self, app):
        """Test get_club_membership() with non-existent club."""
        with app.app_context():
            contact = Contact.query.first()
            assert contact is not None
            
            # Use a very high club ID that shouldn't exist
            membership = contact.get_club_membership(999999)
            assert membership is None, "Should return None for non-existent club"


class TestContactClubRelationships:
    """Tests for ContactClub model relationships."""
    
    def test_contact_club_contact_relationship(self, app):
        """Test ContactClub.contact relationship."""
        with app.app_context():
            cc = ContactClub.query.first()
            assert cc is not None
            
            assert hasattr(cc, 'contact'), "ContactClub should have contact attribute"
            assert cc.contact is not None, "ContactClub.contact should not be None"
            assert isinstance(cc.contact, Contact), "Should be a Contact instance"
            assert cc.contact.id == cc.contact_id
    
    def test_contact_club_club_relationship(self, app):
        """Test ContactClub.club relationship."""
        with app.app_context():
            cc = ContactClub.query.first()
            assert cc is not None
            
            assert hasattr(cc, 'club'), "ContactClub should have club attribute"
            assert cc.club is not None, "ContactClub.club should not be None"
            assert isinstance(cc.club, Club), "Should be a Club instance"
            assert cc.club.id == cc.club_id


class TestMultiClubDataIntegrity:
    """Tests for overall multi-club data integrity."""
    
    def test_no_orphaned_contact_clubs(self, app):
        """Test that all contact_clubs reference valid contacts and clubs."""
        with app.app_context():
            contact_clubs = ContactClub.query.all()
            
            for cc in contact_clubs:
                contact = Contact.query.get(cc.contact_id)
                assert contact is not None, \
                    f"ContactClub {cc.id} references non-existent contact {cc.contact_id}"
                
                club = Club.query.get(cc.club_id)
                assert club is not None, \
                    f"ContactClub {cc.id} references non-existent club {cc.club_id}"
    
    def test_club_has_meetings(self, app):
        """Test that clubs with meetings can be queried."""
        with app.app_context():
            club = Club.query.first()
            assert club is not None
            
            # Test that we can query meetings for this club
            meetings = Meeting.query.filter_by(club_id=club.id).all()
            # Note: Not asserting count > 0 as a new club might not have meetings yet
            assert isinstance(meetings, list), "Should return a list of meetings"
    
    def test_contact_club_to_dict(self, app):
        """Test ContactClub.to_dict() method."""
        with app.app_context():
            cc = ContactClub.query.first()
            assert cc is not None
            
            cc_dict = cc.to_dict()
            assert isinstance(cc_dict, dict)
            assert 'id' in cc_dict
            assert 'contact_id' in cc_dict
            assert 'club_id' in cc_dict
            assert 'membership_type' in cc_dict
            assert 'is_primary' in cc_dict
