from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import db
from .models import Achievement, Contact, Pathway
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .club_context import get_current_club_id
from flask_login import current_user
from datetime import datetime, date
from .services.blockchain_service import record_level as record_level_completion_on_chain
from .services.achievement_service import AchievementService
from flask import jsonify
import logging

achievements_bp = Blueprint('achievements_bp', __name__)

@achievements_bp.route('/achievements')
@login_required
def show_achievements():
    if not is_authorized(Permissions.ACHIEVEMENTS_VIEW):
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    achievements = Achievement.query.join(Contact).all()
    
    # Redirect to settings page with achievements tab
    return redirect(url_for('settings_bp.settings', default_tab='achievements'))

@achievements_bp.route('/achievement/form', defaults={'id': None}, methods=['GET', 'POST'])
@achievements_bp.route('/achievement/form/<int:id>', methods=['GET', 'POST'])
@login_required
def achievement_form(id):
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('settings_bp.settings', default_tab='achievements'))

    achievement = None
    if id:
        achievement = db.get_or_404(Achievement, id)

    if request.method == 'POST':
        contact_id = request.form.get('contact_id')
        issue_date_str = request.form.get('issue_date')
        achievement_type = request.form.get('achievement_type')
        path_name = request.form.get('path_name')
        level = request.form.get('level')
        notes = request.form.get('notes')
        member_id = None
        if contact_id:
            contact = db.session.get(Contact, contact_id)
            if contact:
                member_id = contact.Member_ID

        try:
            issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(request.url)

        # Check for duplicate
        # We consider a duplicate if contact, type, path, and level match.
        if not achievement_type:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'success': False, 'message': 'Achievement type is required.'}, 400
            flash('Achievement type is required.', 'error')
            return redirect(url_for('settings_bp.settings', default_tab='achievements'))


        uid = None
        if contact_id:
            contact = db.session.get(Contact, contact_id)
            if contact:
                uid = contact.user_id

        if uid:
            existing_query = Achievement.query.filter(
                db.or_(Achievement.user_id == uid, Achievement.contact_id == contact_id),
                Achievement.achievement_type == achievement_type,
                Achievement.path_name == (path_name if path_name else None),
                Achievement.level == (int(level) if level else None)
            )
        else:
            existing_query = Achievement.query.filter_by(
                contact_id=contact_id,
                achievement_type=achievement_type,
                path_name=path_name if path_name else None,
                level=int(level) if level else None
            )
        
        if id:
            # If editing, exclude self
            existing_query = existing_query.filter(Achievement.id != id)
            
        existing = existing_query.first()
        
        if existing:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return {'success': False, 'message': 'This achievement already exists for this member.'}, 400
            flash('This achievement already exists for this member.', 'duplicate_warning')
            return redirect(url_for('settings_bp.settings', default_tab='achievements'))

        if not achievement:
            achievement = Achievement()
            db.session.add(achievement)

        achievement.contact_id = contact_id
        achievement.issue_date = issue_date
        achievement.achievement_type = achievement_type
        achievement.path_name = path_name
        achievement.level = int(level) if level else None
        
        # Auto-add lower levels if this is a level completion
        if achievement_type == 'level-completion':
            full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.display_name
            user_ident = f"{full_name} ({current_user.home_club.short_name})" if getattr(current_user, 'home_club', None) and current_user.home_club.short_name else f"{full_name} (ID: {current_user.id})"
            # Record it on the blockchain if it's a new or updated achievement (not just editing notes)
            # Since this takes an active network request, we'll try/except to prevent it from crashing the route
            try:
                success = record_level_completion_on_chain(member_id, path_name, achievement.level, issue_date, user_ident)
                if not success:
                    flash(f"Warning: Failed to record level {achievement.level} completion on blockchain, but it will be saved to the database.", "warning")
            except Exception as e:
                logging.error(f"Failed to record level completion on chain: {e}")
                flash(f"Warning: Exception while recording level {achievement.level} on blockchain. Saved to database.", "warning")
                
            if achievement.level and achievement.level > 1:
                for i in range(1, achievement.level):
                    # Check if lower level achievement exists
                    lower_exists = Achievement.query.filter_by(
                        contact_id=contact_id,
                        achievement_type='level-completion',
                        path_name=path_name,
                        level=i
                    ).first()
                    
                    if not lower_exists:
                        new_lower = Achievement(
                            contact_id=contact_id,
                            member_id=member_id,
                            issue_date=issue_date,
                            achievement_type='level-completion',
                            path_name=path_name,
                            level=i,
                            notes=f"Auto-added based on Level {achievement.level} completion"
                        )
                        db.session.add(new_lower)
                        
                        # Also record the auto-added lower level on the blockchain
                        try:
                            import time
                            time.sleep(2) # Prevent nonce collisions on RPC provider for back-to-back txn
                            success_l = record_level_completion_on_chain(member_id, path_name, i, issue_date, user_ident)
                            if not success_l:
                                logging.warning(f"Warning: Failed to record auto-added level {i} on blockchain.")
                        except Exception as e:
                            logging.error(f"Failed to record auto-added level {i} on chain: {e}")

        achievement.notes = notes
        achievement.member_id = member_id
        
        db.session.commit()
        from .utils import sync_contact_metadata
        sync_contact_metadata(contact_id)

        db.session.commit()
        flash('Achievement saved successfully.', 'success')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return {'success': True}
            
        return redirect(url_for('settings_bp.settings', default_tab='achievements'))

    contacts = Contact.query.filter(Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    
    # Categorize pathways for dynamic frontend filtering
    pathways = [p.name for p in Pathway.query.filter_by(type='pathway').order_by(Pathway.name).all()]
    programs = [p.name for p in Pathway.query.filter_by(type='program').order_by(Pathway.name).all()]
    
    project_types = ['level-completion', 'path-completion', 'program-completion']

    return render_template('achievement_form.html', 
                           achievement=achievement, 
                           contacts=contacts, 
                           pathways=pathways,
                           programs=programs,
                           project_types=project_types)

@achievements_bp.route('/achievement/delete/<int:id>', methods=['POST'])
@login_required
def delete_achievement(id):
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('settings_bp.settings', default_tab='achievements'))

    achievement = Achievement.query.get_or_404(id)
    contact_id = achievement.contact_id
    
    # If this is a level completion, attempt to revoke it on the blockchain first
    if achievement.achievement_type == 'level-completion' and achievement.member_id and achievement.path_name and achievement.level:
        try:
            from .services.blockchain_service import BlockchainService
            full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.display_name
            user_ident = f"{full_name} ({current_user.home_club.short_name})" if getattr(current_user, 'home_club', None) and current_user.home_club.short_name else f"{full_name} (ID: {current_user.id})"
            
            success = BlockchainService.revoke_level(
                member_no=achievement.member_id,
                path_name=achievement.path_name,
                level=achievement.level,
                issue_date=achievement.issue_date,
                user_identifier=user_ident
            )
            if not success:
                logging.warning(f"Failed to record revocation on chain for level {achievement.level}, but proceeding with local delete.")
        except Exception as e:
            logging.error(f"Failed to revoke level completion on chain: {e}")

    db.session.delete(achievement)
    db.session.commit()
    
    from .utils import sync_contact_metadata
    sync_contact_metadata(contact_id)
    flash('Achievement deleted successfully.', 'success')
    return redirect(url_for('settings_bp.settings', default_tab='achievements'))

@achievements_bp.route('/achievements/record', methods=['POST'])
@login_required
def api_record_achievement():
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    data = request.get_json()
    user_id = data.get('user_id')
    achievement_type = data.get('achievement_type')
    issue_date_str = data.get('issue_date')
    path_name = data.get('path_name')
    level = data.get('level')
    notes = data.get('notes')

    if not user_id or not achievement_type:
        return jsonify({'success': False, 'message': 'Missing required fields (user_id, achievement_type).'}), 400

    try:
        issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date() if issue_date_str else date.today()
        achievement = AchievementService.record_achievement(
            user_id=user_id,
            requestor_id=current_user.id,
            achievement_type=achievement_type,
            issue_date=issue_date,
            path_name=path_name,
            level=level,
            notes=notes
        )
        return jsonify({'success': True, 'message': 'Achievement recorded successfully.', 'achievement_id': achievement.id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@achievements_bp.route('/achievements/revoke', methods=['POST'])
@login_required
def api_revoke_achievement():
    if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    data = request.get_json()
    achievement_id = data.get('achievement_id')

    # Support lookup by user_id + type + path + level (from roadmap buttons)
    if not achievement_id:
        user_id = data.get('user_id')
        achievement_type = data.get('achievement_type')
        path_name = data.get('path_name')
        level = data.get('level')
        
        if user_id and achievement_type:
            achievement = Achievement.query.filter_by(
                user_id=user_id,
                achievement_type=achievement_type,
                path_name=path_name,
                level=level
            ).first()
            if achievement:
                achievement_id = achievement.id
    
    if not achievement_id:
        return jsonify({'success': False, 'message': 'Achievement not found.'}), 400

    try:
        AchievementService.revoke_achievement(achievement_id, current_user.id)
        return jsonify({'success': True, 'message': 'Achievement revoked successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@achievements_bp.route('/achievements/status', methods=['GET'])
@login_required
def get_achievement_status():
    user_id = request.args.get('user_id')
    achievement_type = request.args.get('achievement_type')
    path_name = request.args.get('path_name')
    level = request.args.get('level')

    if not user_id or not achievement_type:
        return jsonify({'success': False, 'message': 'Missing user_id or achievement_type.'}), 400

    query = Achievement.query.filter_by(
        user_id=user_id,
        achievement_type=achievement_type
    )
    if path_name:
        query = query.filter_by(path_name=path_name)
    if level:
        try:
            query = query.filter_by(level=int(level))
        except (ValueError, TypeError):
            pass

    achievement = query.first()
    if achievement:
        return jsonify({
            'exists': True,
            'id': achievement.id,
            'issue_date': achievement.issue_date.strftime('%Y-%m-%d'),
            'notes': achievement.notes
        })
    else:
        return jsonify({'exists': False})
