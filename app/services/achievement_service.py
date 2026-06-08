from .. import db
from ..models import Achievement, User
import logging

logger = logging.getLogger(__name__)

class AchievementService:
    @staticmethod
    def record_achievement(user_id, requestor_id, achievement_type, award_date, path_name=None, level=None, notes=None):
        """
        Records an achievement in the database.

        For level-completion: auto-adds missing lower levels (1..N-1) and, when
        level 5 is completed, also records a path-completion achievement.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        # Ensure member_no is available for global tracking
        member_no = user.member_no

        achievement = Achievement(
            user_id=user_id,
            requestor_id=requestor_id,
            achievement_type=achievement_type,
            award_date=award_date,
            path_name=path_name,
            level=level,
            notes=notes,
            member_id=member_no
        )
        db.session.add(achievement)

        if achievement_type == 'level-completion' and level:
            level_int = int(level)
            if level_int > 1:
                for i in range(1, level_int):
                    exists = Achievement.query.filter_by(
                        user_id=user_id,
                        achievement_type='level-completion',
                        path_name=path_name,
                        level=i
                    ).first()
                    if not exists:
                        db.session.add(Achievement(
                            user_id=user_id,
                            requestor_id=requestor_id,
                            achievement_type='level-completion',
                            award_date=award_date,
                            path_name=path_name,
                            level=i,
                            notes=f"Auto-added based on Level {level_int} completion",
                            member_id=member_no
                        ))

            if level_int == 5:
                path_exists = Achievement.query.filter_by(
                    user_id=user_id,
                    achievement_type='path-completion',
                    path_name=path_name
                ).first()
                if not path_exists:
                    db.session.add(Achievement(
                        user_id=user_id,
                        requestor_id=requestor_id,
                        achievement_type='path-completion',
                        award_date=award_date,
                        path_name=path_name,
                        notes="Auto-added based on Level 5 completion",
                        member_id=member_no
                    ))

        db.session.commit()
        return achievement

    @staticmethod
    def revoke_achievement(achievement_id, requestor_id):
        """
        Revokes an achievement.

        For a level-completion: also revokes all higher level-completions and
        the path-completion (if present) for the same user/path, so the path
        returns to a consistent state.
        """
        achievement = db.session.get(Achievement, achievement_id)
        if not achievement:
            raise ValueError(f"Achievement with ID {achievement_id} not found.")

        # Determine whether this revoke should also flip a ContactPath back
        # to 'working' (so the path drops out of the contact's completed list).
        reset_path = False
        user_id = achievement.user_id
        path_name = achievement.path_name

        if achievement.achievement_type == 'path-completion':
            reset_path = True
        elif achievement.achievement_type == 'level-completion' and achievement.level is not None:
            revoked_level = achievement.level

            # Revoke any higher level-completions on the same path
            higher_levels = Achievement.query.filter(
                Achievement.user_id == user_id,
                Achievement.achievement_type == 'level-completion',
                Achievement.path_name == path_name,
                Achievement.level > revoked_level
            ).all()
            for higher in higher_levels:
                db.session.delete(higher)

            # Revoking ANY level on a completed path invalidates the path-completion:
            # the path is no longer fully completed. Drop it.
            path_complete = Achievement.query.filter_by(
                user_id=user_id,
                achievement_type='path-completion',
                path_name=path_name
            ).first()
            if path_complete:
                db.session.delete(path_complete)
                reset_path = True

        if reset_path and path_name:
            from ..models.contact_path import ContactPath
            from ..models.project import Pathway
            user = db.session.get(User, user_id)
            if user:
                contact_id = user.contact_id
                if contact_id:
                    pathway = Pathway.query.filter_by(name=path_name).first()
                    if pathway:
                        cp = ContactPath.query.filter_by(
                            contact_id=contact_id,
                            path_id=pathway.id
                        ).first()
                        if cp and cp.status == 'completed':
                            cp.status = 'working'
                            cp.completed_date = None

        db.session.delete(achievement)
        db.session.commit()

        return True
