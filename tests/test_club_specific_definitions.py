import pytest
from app import db
from app.models.club import Club
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.services.data_import_service import DataImportService
from app.commands.create_club import import_initial_data

def test_club_specific_definitions(app):
    with app.app_context():
        # 0. Create Global Club and Seed Data (Required for new import logic)
        from app.constants import GLOBAL_CLUB_ID
        global_club = Club(id=GLOBAL_CLUB_ID, club_no="Global", club_name="Global Club")
        db.session.add(global_club)
        db.session.flush() # Ensure ID is set
        
        # Seed Global Roles
        r1 = MeetingRole(name="Toastmaster", type="standard", club_id=GLOBAL_CLUB_ID, needs_approval=True, has_single_owner=False, is_member_only=True)
        r2 = MeetingRole(name="General Evaluator", type="standard", club_id=GLOBAL_CLUB_ID, needs_approval=True, has_single_owner=False, is_member_only=False)
        db.session.add_all([r1, r2])
        db.session.flush()
        
        # Seed Global Session Types
        st1 = SessionType(Title="Toastmaster Session", role_id=r1.id, club_id=GLOBAL_CLUB_ID)
        st2 = SessionType(Title="GE Session", role_id=r2.id, club_id=GLOBAL_CLUB_ID)
        db.session.add_all([st1, st2])
        db.session.commit()

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
        club = Club(id=999, club_no="IMPORT01", club_name="Import Club")
        db.session.add(club)
        db.session.commit()

        service = DataImportService("IMPORT01")
        service.resolve_club()
        
        # Mock role data
        roles_data = [
            (1, "Custom Role 1", "icon", "club-specific", "cat", 1, 0, 1),
            (2, "Custom Role 2", "icon", "club-specific", "cat", 1, 0, 0)
        ]
        service.import_meeting_roles(roles_data)
        
        # Verify roles are linked to the club
        roles = MeetingRole.query.filter_by(club_id=club.id).all()
        assert len(roles) == 2
        assert {r.name for r in roles} == {"Custom Role 1", "Custom Role 2"}

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
        custom_role_1 = MeetingRole.query.filter_by(name="Custom Role 1", club_id=club.id).first()
        assert st.role_id == custom_role_1.id

def test_duplicate_names_in_different_clubs(app):
    with app.app_context():
        club1 = Club(club_no="C1", club_name="Club 1")
        club2 = Club(club_no="C2", club_name="Club 2")
        db.session.add(club1)
        db.session.add(club2)
        db.session.flush()

        # Should be allowed in different clubs
        role1 = MeetingRole(name="SameName", type="standard", club_id=club1.id, needs_approval=False, has_single_owner=False)
        role2 = MeetingRole(name="SameName", type="standard", club_id=club2.id, needs_approval=False, has_single_owner=False)
        db.session.add(role1)
        db.session.add(role2)
        
        st1 = SessionType(Title="SameTitle", club_id=club1.id)
        st2 = SessionType(Title="SameTitle", club_id=club2.id)
        db.session.add(st1)
        db.session.add(st2)
        
        db.session.commit()

        assert MeetingRole.query.filter_by(name="SameName").count() == 2
        assert SessionType.query.filter_by(Title="SameTitle").count() == 2

def test_duplicate_names_in_same_club_fails(app):
    with app.app_context():
        club1 = Club(club_no="C3", club_name="Club 3")
        db.session.add(club1)
        db.session.flush()

        role1 = MeetingRole(name="Unique", type="standard", club_id=club1.id, needs_approval=False, has_single_owner=False)
        db.session.add(role1)
        db.session.commit()

        # Adding same name to same club should trigger integrity error or unique constraint
        import sqlalchemy
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            role2 = MeetingRole(name="Unique", type="standard", club_id=club1.id, needs_approval=False, has_single_owner=False)
            db.session.add(role2)
            db.session.commit()
        db.session.rollback()

        st1 = SessionType(Title="UniqueSession", club_id=club1.id)
        db.session.add(st1)
        db.session.commit()

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            st2 = SessionType(Title="UniqueSession", club_id=club1.id)
            db.session.add(st2)
            db.session.commit()
        db.session.rollback()
