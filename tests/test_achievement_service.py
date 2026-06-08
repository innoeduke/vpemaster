from app.models import db, User, Achievement
from app.services.achievement_service import AchievementService
from datetime import date


def test_level_5_auto_completes_path(app, default_club):
    with app.app_context():
        user = User.query.filter_by(member_no='M001').first()
        if not user:
            user = User(username='level5user', member_no='M001', email='l5@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        # Clean any prior achievements for this user/path
        Achievement.query.filter_by(user_id=user_id, path_name='Dynamic Leadership').delete()
        db.session.commit()

        AchievementService.record_achievement(
            user_id=user_id,
            requestor_id=user_id,
            achievement_type='level-completion',
            award_date=date.today(),
            path_name='Dynamic Leadership',
            level=5,
            notes='test'
        )

        records = Achievement.query.filter_by(
            user_id=user_id, path_name='Dynamic Leadership'
        ).all()
        types_levels = sorted([(r.achievement_type, r.level) for r in records])
        # Levels 1..5 + path-completion
        assert types_levels == [
            ('level-completion', 1),
            ('level-completion', 2),
            ('level-completion', 3),
            ('level-completion', 4),
            ('level-completion', 5),
            ('path-completion', None),
        ]


def test_level_3_does_not_complete_path(app, default_club):
    with app.app_context():
        user = User.query.filter_by(member_no='M002').first()
        if not user:
            user = User(username='level3user', member_no='M002', email='l3@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        Achievement.query.filter_by(user_id=user_id, path_name='Visionary Communication').delete()
        db.session.commit()

        AchievementService.record_achievement(
            user_id=user_id,
            requestor_id=user_id,
            achievement_type='level-completion',
            award_date=date.today(),
            path_name='Visionary Communication',
            level=3,
            notes='test'
        )

        records = Achievement.query.filter_by(
            user_id=user_id, path_name='Visionary Communication'
        ).all()
        types_levels = sorted([(r.achievement_type, r.level) for r in records])
        assert types_levels == [
            ('level-completion', 1),
            ('level-completion', 2),
            ('level-completion', 3),
        ]


def test_idempotent_when_levels_already_exist(app, default_club):
    with app.app_context():
        user = User.query.filter_by(member_no='M003').first()
        if not user:
            user = User(username='idemuser', member_no='M003', email='id@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        Achievement.query.filter_by(user_id=user_id, path_name='Pathway L5').delete()
        db.session.commit()

        # Pre-record levels 1..4
        for lvl in range(1, 5):
            AchievementService.record_achievement(
                user_id=user_id,
                requestor_id=user_id,
                achievement_type='level-completion',
                award_date=date.today(),
                path_name='Pathway L5',
                level=lvl,
            )

        # Now record level 5 — should not duplicate
        AchievementService.record_achievement(
            user_id=user_id,
            requestor_id=user_id,
            achievement_type='level-completion',
            award_date=date.today(),
            path_name='Pathway L5',
            level=5,
        )

        records = Achievement.query.filter_by(
            user_id=user_id, path_name='Pathway L5'
        ).all()
        # 5 level-completions + 1 path-completion
        assert len(records) == 6


def test_revoke_level_3_clears_4_5_and_path(app, default_club):
    with app.app_context():
        user = User.query.filter_by(member_no='M004').first()
        if not user:
            user = User(username='revuser', member_no='M004', email='rev@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        path = 'Revoke Path'
        Achievement.query.filter_by(user_id=user_id, path_name=path).delete()
        db.session.commit()

        # Build up a full path completion
        AchievementService.record_achievement(
            user_id=user_id, requestor_id=user_id,
            achievement_type='level-completion', award_date=date.today(),
            path_name=path, level=5,
        )

        before = Achievement.query.filter_by(user_id=user_id, path_name=path).all()
        # 5 levels + path-completion
        assert len(before) == 6

        # Revoke level 3
        lvl3 = Achievement.query.filter_by(
            user_id=user_id, achievement_type='level-completion',
            path_name=path, level=3,
        ).first()
        AchievementService.revoke_achievement(lvl3.id, user_id)

        remaining = Achievement.query.filter_by(user_id=user_id, path_name=path).all()
        remaining_types = sorted([(r.achievement_type, r.level) for r in remaining])
        # Levels 1..2 should remain; 3,4,5 and path-completion should be gone
        assert remaining_types == [
            ('level-completion', 1),
            ('level-completion', 2),
        ]


def test_revoke_level_1_keeps_only_level_1(app, default_club):
    with app.app_context():
        user = User.query.filter_by(member_no='M005').first()
        if not user:
            user = User(username='rev1user', member_no='M005', email='rev1@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        path = 'Revoke One Path'
        Achievement.query.filter_by(user_id=user_id, path_name=path).delete()
        db.session.commit()

        AchievementService.record_achievement(
            user_id=user_id, requestor_id=user_id,
            achievement_type='level-completion', award_date=date.today(),
            path_name=path, level=4,
        )

        lvl1 = Achievement.query.filter_by(
            user_id=user_id, achievement_type='level-completion',
            path_name=path, level=1,
        ).first()
        AchievementService.revoke_achievement(lvl1.id, user_id)

        remaining = Achievement.query.filter_by(user_id=user_id, path_name=path).all()
        # Higher levels 2,3,4 + path-completion all gone
        assert remaining == []


def test_revoke_middle_level_after_path_completion_drops_path(app, default_club):
    """If a path is completed (has path-completion + all 5 levels), revoking
    a middle level should also drop the path-completion."""
    with app.app_context():
        user = User.query.filter_by(member_no='M006').first()
        if not user:
            user = User(username='midrev', member_no='M006', email='mid@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        path = 'Completed Path'
        Achievement.query.filter_by(user_id=user_id, path_name=path).delete()
        db.session.commit()

        # Record all 5 levels -> path-completion auto-added
        for lvl in range(1, 6):
            AchievementService.record_achievement(
                user_id=user_id, requestor_id=user_id,
                achievement_type='level-completion', award_date=date.today(),
                path_name=path, level=lvl,
            )

        before = Achievement.query.filter_by(user_id=user_id, path_name=path).all()
        # 5 levels + path-completion
        assert len(before) == 6
        assert any(r.achievement_type == 'path-completion' for r in before)

        # Revoke level 3 (a middle level)
        lvl3 = Achievement.query.filter_by(
            user_id=user_id, achievement_type='level-completion',
            path_name=path, level=3,
        ).first()
        AchievementService.revoke_achievement(lvl3.id, user_id)

        remaining = Achievement.query.filter_by(user_id=user_id, path_name=path).all()
        remaining_types = sorted([(r.achievement_type, r.level) for r in remaining])
        # path-completion gone, only levels 1-2 remain
        assert ('path-completion', None) not in remaining_types
        assert remaining_types == [
            ('level-completion', 1),
            ('level-completion', 2),
        ]


def test_revoke_path_completion_resets_contact_path_to_working(app, default_club):
    """Revoking the path-completion should flip the matching ContactPath
    from 'completed' back to 'working' so it drops out of Completed_Paths."""
    from app.models import Contact, ContactPath, Pathway

    with app.app_context():
        user = User.query.filter_by(member_no='M007').first()
        if not user:
            user = User(username='resetuser', member_no='M007', email='reset@test.com')
            user.set_password('pw')
            db.session.add(user)
            db.session.commit()

        user_id = user.id
        path_name = 'Reset Path'

        # Ensure contact is linked to user via UserClub
        from app.models import UserClub
        contact = Contact(Name='Reset Contact', Type='Member', first_name='Reset', last_name='Contact')
        db.session.add(contact)
        db.session.commit()
        user_club = UserClub(user_id=user.id, contact_id=contact.id, club_id=default_club.id)
        db.session.add(user_club)
        db.session.commit()

        # Ensure pathway exists
        pathway = Pathway.query.filter_by(name=path_name).first()
        if not pathway:
            pathway = Pathway(name=path_name, abbr='RP', type='pathway', status='active')
            db.session.add(pathway)
            db.session.commit()

        # Clean prior state
        Achievement.query.filter_by(user_id=user_id, path_name=path_name).delete()
        ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).delete()
        db.session.commit()

        # Register and complete the path
        cp = ContactPath(contact_id=contact.id, path_id=pathway.id, status='completed')
        db.session.add(cp)
        db.session.commit()
        AchievementService.record_achievement(
            user_id=user_id, requestor_id=user_id,
            achievement_type='path-completion', award_date=date.today(),
            path_name=path_name,
        )

        # Confirm ContactPath is completed
        cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
        assert cp.status == 'completed'

        # Revoke the path-completion
        pc = Achievement.query.filter_by(
            user_id=user_id, achievement_type='path-completion', path_name=path_name
        ).first()
        AchievementService.revoke_achievement(pc.id, user_id)

        # ContactPath should be flipped back to 'working'
        cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
        assert cp.status == 'working'
        assert cp.completed_date is None
