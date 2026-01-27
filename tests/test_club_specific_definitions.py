import pytest
from app import db
from app.models.club import Club
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.services.data_import_service import DataImportService
from scripts.create_club import import_initial_data

def test_club_specific_definitions(app):
    with app.app_context():
        # 1. Create two clubs
        club1 = Club(club_no="TEST01", club_name="Test Club 1")
        club2 = Club(club_no="TEST02", club_name="Test Club 2")
        db.session.add(club1)
        db.session.add(club2)
        db.session.flush()

        # 2. Import initial data for both
        import_initial_data(club1)
        import_initial_data(club2)
        db.session.commit()

        # 3. Verify they have different records but with same names/titles
        roles1 = MeetingRole.query.filter_by(club_id=club1.id).all()
        roles2 = MeetingRole.query.filter_by(club_id=club2.id).all()
        
        assert len(roles1) > 0
        assert len(roles2) > 0
        assert len(roles1) == len(roles2)
        
        role_names1 = {r.name for r in roles1}
        role_names2 = {r.name for r in roles2}
        assert role_names1 == role_names2
        
        # Verify IDs are different
        role_ids1 = {r.id for r in roles1}
        role_ids2 = {r.id for r in roles2}
        assert role_ids1.isdisjoint(role_ids2)

        st1 = SessionType.query.filter_by(club_id=club1.id).all()
        st2 = SessionType.query.filter_by(club_id=club2.id).all()
        
        assert len(st1) > 0
        assert len(st2) > 0
        assert len(st1) == len(st2)
        
        st_titles1 = {s.Title for s in st1}
        st_titles2 = {s.Title for s in st2}
        assert st_titles1 == st_titles2
        
        # Verify IDs are different
        st_ids1 = {s.id for s in st1}
        st_ids2 = {s.id for s in st2}
        assert st_ids1.isdisjoint(st_ids2)

def test_data_import_service_club_id(app):
    with app.app_context():
        # Create a club
        club = Club(club_no="IMPORT01", club_name="Import Club")
        db.session.add(club)
        db.session.commit()

        service = DataImportService("IMPORT01")
        service.resolve_club()
        
        # Mock role data
        roles_data = [
            (1, "Toastmaster", "icon", "type", "cat", 1, 0, 1),
            (2, "General Evaluator", "icon", "type", "cat", 1, 0, 0)
        ]
        service.import_meeting_roles(roles_data)
        
        # Verify roles are linked to the club
        roles = MeetingRole.query.filter_by(club_id=club.id).all()
        assert len(roles) == 2
        assert {r.name for r in roles} == {"Toastmaster", "General Evaluator"}

        # Mock session type data (RoleID 1 maps to Toastmaster)
        types_data = [
            (1, "Opening", 0, 0, 1, 0, 0, 0, 0, 1)
        ]
        service.import_session_types(types_data)
        
        # Verify session types are linked to the club
        st = SessionType.query.filter_by(club_id=club.id).first()
        assert st is not None
        assert st.Title == "Opening"
        assert st.club_id == club.id
        
        # Verify role mapping worked
        toastmaster_role = MeetingRole.query.filter_by(name="Toastmaster", club_id=club.id).first()
        assert st.role_id == toastmaster_role.id
