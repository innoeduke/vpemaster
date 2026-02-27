from .. import db
from ..models import Achievement, User
from .blockchain_service import BlockchainService
import logging

logger = logging.getLogger(__name__)

class AchievementService:
    @staticmethod
    def record_achievement(user_id, requestor_id, achievement_type, issue_date, path_name=None, level=None, notes=None):
        """
        Records an achievement in the database and optionally on the blockchain.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        # Ensure member_no is available for global tracking
        member_no = user.member_no
        if not member_no:
             # Fallback to checking associated contacts if needed, 
             # but user.member_no should be the source of truth now.
             pass

        achievement = Achievement(
            user_id=user_id,
            requestor_id=requestor_id,
            achievement_type=achievement_type,
            issue_date=issue_date,
            path_name=path_name,
            level=level,
            notes=notes,
            member_id=member_no
        )
        db.session.add(achievement)
        db.session.commit()

        # Blockchain integration only for level completion
        if achievement_type == 'level-completion' and member_no:
            requestor = db.session.get(User, requestor_id)
            requestor_name = requestor.username if requestor else "Admin"
            
            logger.info(f"Recording level completion on blockchain for user {user_id}")
            BlockchainService.record_level(
                member_no=member_no,
                path_name=path_name,
                level=level,
                issue_date=issue_date,
                user_identifier=requestor_name
            )

        return achievement

    @staticmethod
    def revoke_achievement(achievement_id, requestor_id):
        """
        Revokes an achievement.
        """
        achievement = db.session.get(Achievement, achievement_id)
        if not achievement:
            raise ValueError(f"Achievement with ID {achievement_id} not found.")

        achievement_type = achievement.achievement_type
        user = achievement.user
        path_name = achievement.path_name
        level = achievement.level
        issue_date = achievement.issue_date
        member_no = achievement.member_id

        db.session.delete(achievement)
        db.session.commit()

        # Blockchain integration only for level completion
        if achievement_type == 'level-completion' and member_no:
            requestor = db.session.get(User, requestor_id)
            requestor_name = requestor.username if requestor else "Admin"
            
            logger.info(f"Revoking level completion on blockchain for user {user.id if user else 'unknown'}")
            BlockchainService.revoke_level(
                member_no=member_no,
                path_name=path_name,
                level=level,
                issue_date=issue_date,
                user_identifier=requestor_name
            )

        return True
