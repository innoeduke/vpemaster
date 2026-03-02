from .. import db
from ..models import Achievement, User
from .blockchain_service import BlockchainService
import logging
import threading
from flask import current_app

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
            app = current_app._get_current_object()
            
            def _background_record(app_ctx, ach_id, m_no, p_name, lvl, i_date, req_name):
                with app_ctx.app_context():
                    try:
                        logger.info(f"Recording level completion on blockchain for user {user_id} (Background)")
                        success = BlockchainService.record_level(
                            member_no=m_no,
                            path_name=p_name,
                            level=lvl,
                            issue_date=i_date,
                            user_identifier=req_name
                        )
                        if not success:
                            raise RuntimeError("Blockchain recording returned False")
                    except Exception as e:
                        logger.error(f"Background blockchain recording failed: {e}. Rolling back DB record {ach_id}")
                        # Rollback: Delete the achievement record
                        failed_ach = db.session.get(Achievement, ach_id)
                        if failed_ach:
                            db.session.delete(failed_ach)
                            db.session.commit()

            requestor = db.session.get(User, requestor_id)
            requestor_name = requestor.username if requestor else "Admin"
            
            thread = threading.Thread(
                target=_background_record,
                args=(app, achievement.id, member_no, path_name, level, issue_date, requestor_name),
                daemon=True
            )
            thread.start()

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
        
        # Store data needed for background task before deletion if we wanted to rollback deletion,
        # but revocation is slightly different. Usually, we delete first. 
        # If revocation fails, we might want to re-add it?
        # For simplicity, let's just delete from DB. If blockchain call fails, the UI and DB stay in sync
        # but blockchain is "stuck". User can retry.

        db.session.delete(achievement)
        db.session.commit()

        # Blockchain integration only for level completion
        if achievement_type == 'level-completion' and member_no:
            app = current_app._get_current_object()
            
            def _background_revoke(app_ctx, m_no, p_name, lvl, i_date, req_name):
                with app_ctx.app_context():
                    try:
                        logger.info(f"Revoking level completion on blockchain (Background)")
                        BlockchainService.revoke_level(
                            member_no=m_no,
                            path_name=p_name,
                            level=lvl,
                            issue_date=i_date,
                            user_identifier=req_name
                        )
                    except Exception as e:
                        logger.error(f"Background blockchain revocation failed: {e}")

            requestor = db.session.get(User, requestor_id)
            requestor_name = requestor.username if requestor else "Admin"
            
            thread = threading.Thread(
                target=_background_revoke,
                args=(app, member_no, path_name, level, issue_date, requestor_name),
                daemon=True
            )
            thread.start()

        return True
