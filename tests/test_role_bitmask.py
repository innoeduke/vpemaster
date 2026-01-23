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
             member_role = AuthRole(name="Member", level=1)
             db_session.add(member_role)
             
        officer_role = AuthRole.get_by_name("Officer")
        if not officer_role:
             officer_role = AuthRole(name="Officer", level=2)
             db_session.add(officer_role)
             
        vpe_role = AuthRole.get_by_name("VPE")
        if not vpe_role:
             vpe_role = AuthRole(name="VPE", level=64)
             db_session.add(vpe_role)
        
        db_session.commit()
        
        # Ensure levels are correct for test
        member_role.level = 1
        officer_role.level = 2
        vpe_role.level = 64
        
        # Also ensure any other roles in DB don't have None level which would break bitwise ops
        other_roles = AuthRole.query.filter(AuthRole.level == None).all()
        for r in other_roles:
            r.level = 0
            
        db_session.commit()

        # Create Club
        club = Club(club_no="BM_1", club_name="Bitmask Club")
        db_session.add(club)
        db_session.commit()

        # Create User
        user = User(username="bitmask_user", email="bm@test.com")
        user.set_password("password")
        db_session.add(user)
        db_session.commit()
        
        # Assign Multiple Roles: Member (1) + VPE (64) = 65
        role_sum = member_role.level + vpe_role.level
        user.set_club_role(club.id, role_sum)
        db_session.commit()
        
        # Verify Storage
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club.id).first()
        assert uc.club_role_level == 65
        
        # Verify Retrieval
        roles = user.get_roles_for_club(club.id)
        assert member_role.name in roles
        assert vpe_role.name in roles
        assert officer_role.name not in roles
        
        # Verify object Roles property
        uc_roles = [r.name for r in uc.roles]
        assert member_role.name in uc_roles
        assert vpe_role.name in uc_roles
        
        # Verify primary (highest) role
        # Assuming get_current_club_id returns context, but primary_role has fallback logic?
        # primary_role logic depends on context. Let's mock context manually or check logic.
        # Logic: return max(roles)
        primary = uc.club_role
        assert primary.name == vpe_role.name
        
        # Add another role: Officer (2) -> Level should be 67
        new_sum = uc.club_role_level + officer_role.level
        user.set_club_role(club.id, new_sum)
        db_session.commit()
        
        uc.club_role_level # refresh
        assert uc.club_role_level == 67
        roles = user.get_roles_for_club(club.id)
        assert len(roles) >= 3 # might contain 'User' implicitly
        assert officer_role.name in roles
        
        print("Bitmask role storage verification passed.")
        
        # Cleanup
        db_session.delete(user)
        db_session.delete(club)
        db_session.commit()
