import pytest
from app.services.data_import_service import DataImportService
from app.models.contact import Contact
from app.models.base import db
from app.models.club import Club

def test_mentor_remapping_success(app, default_club):
    """Test that mentor_id is correctly remapped using the contact map during import."""
    with app.app_context():
        # Ensure club matches
        service = DataImportService(default_club.club_no)
        service.club_id = default_club.id
        
        # Mock contacts data from backup
        # Schema: 0:id, 1:Name, 2:Club, 3:Date_Created, 4:Type, 5:DTM, 6:Completed_Paths, 
        # 7:Phone_Number, 8:Bio, 9:Email, 10:Member_ID, 11:Mentor_ID, 12:Current_Path, 
        # 13:Next_Project, 14:credentials, 15:Avatar_URL
        
        contacts_data = [
            (101, 'Mentor John', None, '2023-01-01', 'Member', 0, None, None, None, 'mentor@test.com', 'M001', None, None, None, None, None),
            (102, 'Mentee Jane', None, '2023-01-01', 'Member', 0, None, None, None, 'mentee@test.com', 'M002', 101, None, None, None, None)
        ]
        
        # Run import
        service.import_contacts(contacts_data)
        
        # Verify in database
        mentor = Contact.query.filter_by(Name='Mentor John').first()
        mentee = Contact.query.filter_by(Name='Mentee Jane').first()
        
        assert mentor is not None, "Mentor should be imported"
        assert mentee is not None, "Mentee should be imported"
        assert mentor.Email == 'mentor@test.com'
        assert mentee.Email == 'mentee@test.com'
        assert mentee.Mentor_ID == mentor.id, f"Mentee's Mentor_ID should be {mentor.id}, but got {mentee.Mentor_ID}"

def test_mentor_remapping_legacy_string(app, default_club):
    """Test that mentor_id can still be remapped using Member_ID string for legacy support."""
    with app.app_context():
        service = DataImportService(default_club.club_no)
        service.club_id = default_club.id
        
        # Pre-seed a mentor in the database with a Member_ID
        mentor_existing = Contact(Name='Legacy Mentor', Member_ID='LM001', Email='legacy@test.com')
        db.session.add(mentor_existing)
        db.session.commit()
        
        # Mentee from backup referencing mentor by Member_ID string
        contacts_data = [
            (201, 'Legacy Mentee', None, '2023-01-01', 'Member', 0, None, None, None, 'l_mentee@test.com', 'M003', 'LM001', None, None, None, None)
        ]
        
        service.import_contacts(contacts_data)
        
        mentee = Contact.query.filter_by(Name='Legacy Mentee').first()
        assert mentee is not None
        assert mentee.Mentor_ID == mentor_existing.id, "Should fallback to Member_ID string mapping"
