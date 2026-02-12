"""
Test that path-completion and program-completion achievements are imported
into the new club when an existing user is added to it.
"""
import pytest
from datetime import date


def test_ensure_contact_clones_achievements(app, default_club):
    """When a user with achievements in Club A joins Club B,
    path-completion and program-completion records are cloned with
    club_id = Club B.  level-completion records are NOT cloned."""
    with app.app_context():
        from app import db
        from app.models import User, Club, Contact, ContactClub, UserClub, Achievement

        # --- Setup ---
        club_a = default_club             # already created by fixture
        club_b = Club(club_name="Second Club", club_no="999777")
        db.session.add(club_b)
        db.session.commit()

        # Create user + contact in Club A
        user = User(username="multi_ach_user", email="multi_ach@test.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        contact_a = Contact(
            Name="Multi Ach User",
            Email="multi_ach@test.com",
            Type="Member",
            Date_Created=date.today(),
            Member_ID="TM123",
            Current_Path="Dynamic Leadership",
        )
        db.session.add(contact_a)
        db.session.flush()

        db.session.add(ContactClub(contact_id=contact_a.id, club_id=club_a.id))
        db.session.add(UserClub(user_id=user.id, club_id=club_a.id,
                                contact_id=contact_a.id, is_home=True))

        # Add achievements in Club A
        ach_path = Achievement(
            contact_id=contact_a.id, member_id="TM123",
            issue_date=date(2025, 6, 1),
            achievement_type="path-completion",
            path_name="Dynamic Leadership",
            club_id=club_a.id,
        )
        ach_program = Achievement(
            contact_id=contact_a.id, member_id="TM123",
            issue_date=date(2025, 9, 1),
            achievement_type="program-completion",
            path_name="Distinguished Toastmasters",
            club_id=club_a.id,
        )
        ach_level = Achievement(
            contact_id=contact_a.id, member_id="TM123",
            issue_date=date(2025, 3, 1),
            achievement_type="level-completion",
            path_name="Dynamic Leadership",
            level=3,
            club_id=club_a.id,
        )
        db.session.add_all([ach_path, ach_program, ach_level])
        db.session.commit()

        # --- Act: add user to Club B ---
        contact_b = user.ensure_contact(
            full_name="Multi Ach User",
            email="multi_ach@test.com",
            club_id=club_b.id,
        )
        db.session.commit()

        # --- Assert ---
        assert contact_b is not None
        assert contact_b.id != contact_a.id, "Should be a NEW contact"

        # Achievements cloned for Club B
        club_b_achs = Achievement.query.filter_by(
            contact_id=contact_b.id, club_id=club_b.id
        ).all()

        types_cloned = {a.achievement_type for a in club_b_achs}
        assert "path-completion" in types_cloned
        assert "program-completion" in types_cloned
        assert "level-completion" not in types_cloned, \
            "level-completion should NOT be cloned"

        # Verify path names
        path_names = {a.path_name for a in club_b_achs}
        assert "Dynamic Leadership" in path_names
        assert "Distinguished Toastmasters" in path_names

        # Verify basic fields were copied
        assert contact_b.Member_ID == "TM123"
        assert contact_b.Current_Path == "Dynamic Leadership"


def test_ensure_contact_no_duplicate_clone(app, default_club):
    """Calling ensure_contact again should NOT create duplicate achievements."""
    with app.app_context():
        from app import db
        from app.models import User, Club, Contact, ContactClub, UserClub, Achievement

        club_a = default_club
        club_b = Club(club_name="Dup Test Club", club_no="999666")
        db.session.add(club_b)
        db.session.commit()

        user = User(username="dup_test_user", email="dup_test@test.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        contact_a = Contact(
            Name="Dup Test User", Email="dup_test@test.com",
            Type="Member", Date_Created=date.today(),
        )
        db.session.add(contact_a)
        db.session.flush()
        db.session.add(ContactClub(contact_id=contact_a.id, club_id=club_a.id))
        db.session.add(UserClub(user_id=user.id, club_id=club_a.id,
                                contact_id=contact_a.id, is_home=True))
        db.session.add(Achievement(
            contact_id=contact_a.id, issue_date=date(2025, 6, 1),
            achievement_type="path-completion", path_name="Visionary Communication",
            club_id=club_a.id,
        ))
        db.session.commit()

        # First call
        user.ensure_contact(full_name="Dup Test User",
                            email="dup_test@test.com", club_id=club_b.id)
        db.session.commit()

        # Second call (idempotency check)
        user.ensure_contact(full_name="Dup Test User",
                            email="dup_test@test.com", club_id=club_b.id)
        db.session.commit()

        contact_b = user.get_user_club(club_b.id).contact
        count = Achievement.query.filter_by(
            contact_id=contact_b.id, club_id=club_b.id,
            achievement_type="path-completion",
            path_name="Visionary Communication",
        ).count()
        assert count == 1, f"Expected 1 cloned achievement, got {count}"
