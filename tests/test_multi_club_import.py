"""
Test that path-completion and program-completion achievements are imported
into the new club when an existing user is added to it.
"""
import pytest
from datetime import date


def test_ensure_contact_aggregates_centralized_achievements(app, default_club):
    """When a user with achievements joins a new club, the new contact 
    should reflect those achievements via synchronized metadata."""
    with app.app_context():
        from app import db
        from app.models import User, Club, Contact, ContactClub, UserClub, Achievement, Pathway

        # --- Setup ---
        club_a = default_club
        club_b = Club(club_name="Second Club", club_no="999777")
        db.session.add(club_b)
        db.session.commit()

        user = User(username="multi_ach_user", email="multi_ach@test.com")
        user.set_password("password")
        db.session.add(user)
        
        # Seed Pathway for metadata sync to work
        pathway = Pathway(name="Dynamic Leadership", abbr="DL")
        db.session.add(pathway)
        db.session.commit()

        contact_a = user.ensure_contact(club_id=club_a.id)
        contact_a.Current_Path = "Dynamic Leadership"
        db.session.commit()

        # Add achievements linked to USER
        db.session.add(Achievement(
            user_id=user.id,
            issue_date=date(2025, 6, 1),
            achievement_type="path-completion",
            path_name="Dynamic Leadership"
        ))
        db.session.commit()

        # --- Act: add user to Club B ---
        contact_b = user.ensure_contact(
            full_name="Multi Ach User",
            email="multi_ach@test.com",
            club_id=club_b.id,
        )
        # Manually set path for metadata sync to pick up
        contact_b.Current_Path = "Dynamic Leadership"
        db.session.commit()

        # --- Assert ---
        assert contact_b is not None
        assert contact_b.id != contact_a.id
        
        # Verify metadata aggregation from centralized achievements
        # (sync_contact_metadata is called inside ensure_contact)
        from app.utils import sync_contact_metadata
        sync_contact_metadata(contact_b.id) # Ensure it's fresh
        
        assert contact_b.credentials == "DL5"
        assert "DL5" in contact_b.Completed_Paths

def test_ensure_contact_idempotency(app, default_club):
    """Calling ensure_contact again should be idempotent."""
    with app.app_context():
        from app import db
        from app.models import User, Club, Contact, ContactClub, UserClub, Achievement, Pathway

        club_a = default_club
        club_b = Club(club_name="Dup Test Club", club_no="999666")
        db.session.add(club_b)
        db.session.commit()

        user = User(username="dup_test_user", email="dup_test@test.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        # First call
        user.ensure_contact(club_id=club_b.id)
        db.session.commit()
        
        contact_1 = user.get_user_club(club_b.id).contact

        # Second call
        user.ensure_contact(club_id=club_b.id)
        db.session.commit()
        
        contact_2 = user.get_user_club(club_b.id).contact
        assert contact_1.id == contact_2.id
