import pytest
from app.models import User, Club, AuthRole, UserClub
from app.auth.permissions import Permissions

@pytest.fixture
def db_session(app):
    with app.app_context():
        from app import db
        yield db.session
        db.session.remove()

def test_role_bitmask_storage(app, db_session):
    """
    Test that users can have multiple roles in the same club using stored bitmask.
    """
    with app.app_context():
        # Setup Roles with power-of-2 levels if not exist
        member_role = AuthRole.get_by_name(Permissions.USER)
        if not member_role:
             member_role = AuthRole(name=Permissions.USER, level=1)
             db_session.add(member_role)
        else:
             member_role.level = 1
             
        officer_role = AuthRole.get_by_name("Officer")
        if not officer_role:
             officer_role = AuthRole(name="Officer", level=2)
             db_session.add(officer_role)
        else:
             officer_role.level = 2
             
        vpe_role = AuthRole.get_by_name("VPE")
        if not vpe_role:
             vpe_role = AuthRole(name="VPE", level=64)
             db_session.add(vpe_role)
        else:
             vpe_role.level = 64
        
        db_session.commit()
        
        # Also ensure any other roles in DB don't have None level which would break bitwise ops
        other_roles = AuthRole.query.filter(AuthRole.level == None).all()
        for r in other_roles:
            r.level = 0
            
        db_session.commit()
        
        # Clear Role cache to ensure fresh lookup
        AuthRole.clear_role_cache()

        # Create Club
        club = Club(club_no="BM_1", club_name="Bitmask Club")
        db_session.add(club)
        db_session.commit()

        # Create User
        user = User(username="bitmask_user", email="bm@test.com")
        user.set_password("password")
        db_session.add(user)
        db_session.commit()
        
        # Assign Single Role: VPE (64)
        user.set_club_role(club.id, level=vpe_role.level) # 64
        db_session.commit()
        db_session.commit()
        
        # Verify Storage
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club.id).first()
        assert uc.club_role_level == 64
        
        # Verify Retrieval
        roles = user.get_roles_for_club(club.id)
        role_names = [r['name'] for r in roles]
        assert vpe_role.name in role_names
        assert member_role.name not in role_names
        assert officer_role.name not in role_names
        
        # Verify object Roles property
        uc_roles = [r.name for r in uc.roles]
        assert vpe_role.name in uc_roles
        assert member_role.name not in uc_roles
        
        # Verify primary (highest) role
        primary = uc.club_role
        assert primary.name == vpe_role.name
        
        # Add another role: Officer (2)
        user.set_club_role(club.id, level=officer_role.level)
        db_session.commit()
        
        db_session.refresh(uc)
        assert uc.club_role_level == 2
        roles = user.get_roles_for_club(club.id)
        role_names = [r['name'] for r in roles]
        assert officer_role.name in role_names
        assert vpe_role.name not in role_names
        
        print("Bitmask role storage verification passed.")
        
        # Cleanup
        db_session.delete(user)
        db_session.delete(club)
        db_session.commit()
