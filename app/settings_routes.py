# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app, flash
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user
from .club_context import get_current_club_id, authorized_club_required
from .models import SessionType, User, MeetingRole, Achievement, Contact, Permission, AuthRole, RolePermission, PermissionAudit, ContactClub, Club, ExComm, UserClub
from .constants import GLOBAL_CLUB_ID
import json
from . import db
import os
import csv
import io
from datetime import datetime

settings_bp = Blueprint('settings_bp', __name__)


@settings_bp.route('/settings')
@login_required
@authorized_club_required
def settings():
    """
    Renders the settings page, visible only to administrators.
    """
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    # Get current club context
    club_id = get_current_club_id()
    
    # Fetch Global items separately
    global_session_types = SessionType.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
    global_roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()

    # Fetch Local items separately (if not global club)
    local_session_types = []
    local_roles_query = []
    
    if club_id and club_id != GLOBAL_CLUB_ID:
        local_session_types = SessionType.query.filter_by(club_id=club_id).all()
        local_roles_query = MeetingRole.query.filter_by(club_id=club_id).all()
    elif club_id == GLOBAL_CLUB_ID:
        # If we are in the Global Club, "local" lists are empty, or effectively the same as global?
        # Actually, if we are editing Global Club, we treat them as "local" to this club for editing purposes.
        # But per requirements, we want to separate. 
        # If I am Global Admin managing Club 1, I should see them in the "Club Specific" or just one list.
        # Let's treat Club 1 items as "Global" list, and Local list is empty.
        # AND we make the Global list editable for Club 1.
        pass

    # For backward compatibility with existing template (merged list), 
    # we might still need 'session_types' and 'roles_query' IF we were not updating the template.
    # But we ARE updating the template.
    # However, 'roles' (list of dicts) might be used elsewhere or for dropdowns?
    # The 'roles' var in this function is passed to template. 
    # Let's keep 'roles_query' as the MERGED list for dropdowns if needed, or just for safety.
    # Actually, let's reconstruct the merged list for the 'roles' json variable used in JS keys.
    merged_roles = MeetingRole.get_all_for_club(club_id)
    roles = [{'id': role.id, 'name': role.name} for role in merged_roles]
    
    # Users: Filter by club membership
    if club_id:
        all_users = User.query.join(UserClub).filter(
            UserClub.club_id == club_id
        ).options(
            db.joinedload(User.club_memberships)
        ).order_by(User.username.asc()).all()
    else:
        all_users = User.query.options(
            db.joinedload(User.club_memberships)
        ).order_by(User.username.asc()).all()
    
    # Batch populate contacts for the current club to avoid N+1 queries in template
    User.populate_contacts(all_users, club_id)
    
    # Achievements: Filter by club, order by Member Name then Date
    if club_id:
        achievements = Achievement.query.join(Contact).join(ContactClub).filter(
            ContactClub.club_id == club_id
        ).order_by(Contact.Name.asc(), Achievement.issue_date.desc()).all()
    else:
        achievements = Achievement.query.join(Contact).order_by(Contact.Name.asc(), Achievement.issue_date.desc()).all()

    return render_template('settings.html', 
                          global_session_types=global_session_types,
                          local_session_types=local_session_types,
                          global_roles=global_roles,
                          local_roles=local_roles_query,
                          all_users=all_users, 
                          roles=roles, 
                          # We still pass merged lists if the template needs them for something else, 
                          # but mostly we rely on the split lists now.
                          # Actually, let's just make sure we don't break anything.
                          # The original template used 'session_types' and 'roles_query'.
                          # We will replace usages in template.
                          achievements=achievements, club_id=club_id, GLOBAL_CLUB_ID=GLOBAL_CLUB_ID)


@settings_bp.route('/settings/sessions/add', methods=['POST'])
@login_required
def add_session_type():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    try:
        # Input validation and cleaning
        title = request.form.get('title', '').strip()
        if not title:
            return jsonify(success=False, message="Title is required"), 400

        # Get current club context
        club_id = get_current_club_id()

        # Check if title already exists in this club
        existing_session = SessionType.query.filter_by(Title=title, club_id=club_id).first()
        if existing_session:
            return jsonify(success=False, message="Session type with this title already exists in this club"), 400

        # Validate numeric input
        duration_min_str = request.form.get('duration_min', '').strip()
        duration_max_str = request.form.get('duration_max', '').strip()

        duration_min = None
        duration_max = None

        if duration_min_str:
            if not duration_min_str.isdigit():
                return jsonify(success=False, message="Duration min must be a positive integer"), 400
            duration_min = int(duration_min_str)
            if duration_min < 1 or duration_min > 480:  # 8-hour limit
                return jsonify(success=False, message="Duration min must be between 1 and 480 minutes"), 400

        if duration_max_str:
            if not duration_max_str.isdigit():
                return jsonify(success=False, message="Duration max must be a positive integer"), 400
            duration_max = int(duration_max_str)
            if duration_max < 1 or duration_max > 480:
                return jsonify(success=False, message="Duration max must be between 1 and 480 minutes"), 400

        # Validate duration logic
        if duration_min and duration_max and duration_min > duration_max:
            return jsonify(success=False, message="Duration min cannot be greater than duration max"), 400

        role_id_str = request.form.get('role_id', '').strip()
        role_id = int(role_id_str) if role_id_str else None

        new_session = SessionType(
            Title=title,
            role_id=role_id,
            Duration_Min=duration_min,
            Duration_Max=duration_max,
            Is_Section='is_section' in request.form,
            Valid_for_Project='valid_for_project' in request.form,
            Is_Hidden='is_hidden' in request.form,
            club_id=club_id
        )
        db.session.add(new_session)
        db.session.commit()

        # Return the new session object so the frontend can add it to the table
        new_session_data = {
            'id': new_session.id,
            'Title': new_session.Title,
            'role_id': new_session.role_id,
            'Duration_Min': new_session.Duration_Min,
            'Duration_Max': new_session.Duration_Max,
            'Is_Section': new_session.Is_Section,
            'Valid_for_Project': new_session.Valid_for_Project,
            'Is_Hidden': new_session.Is_Hidden
        }
        return jsonify(success=True, message="Session type added successfully", new_session=new_session_data)

    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f"Value error adding session type: {str(e)}")
        return jsonify(success=False, message="Invalid input data"), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding session type: {str(e)}")
        return jsonify(success=False, message="Internal server error"), 500


@settings_bp.route('/settings/sessions/update', methods=['POST'])
@login_required
def update_session_types():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    club_id = get_current_club_id()
    try:
        for item in data:
            session_type = db.session.get(SessionType, item['id'])
            if session_type and session_type.club_id == club_id:
                session_type.Title = item.get('Title')
                role_id_str = item.get('role_id')
                session_type.role_id = int(
                    role_id_str) if role_id_str else None
                session_type.Is_Section = item.get('Is_Section', False)
                session_type.Valid_for_Project = item.get(
                    'Valid_for_Project', False)
                session_type.Is_Hidden = item.get('Is_Hidden', False)

                duration_min = item.get('Duration_Min')
                session_type.Duration_Min = int(
                    duration_min) if duration_min else None

                duration_max = item.get('Duration_Max')
                session_type.Duration_Max = int(
                    duration_max) if duration_max else None

        db.session.commit()
        return jsonify(success=True, message="Session types updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/sessions/delete/<int:id>', methods=['POST'])
@login_required
def delete_session_type(id):
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    club_id = get_current_club_id()
    try:
        session_type = db.session.get(SessionType, id)
        
        # Security: Prevent deletion of Global items by non-sysadmin (or if enforce strict overrides)
        # Even SysAdmin shouldn't delete Global items from a specific club context unless they are managing Club 1 directly.
        if session_type.club_id == GLOBAL_CLUB_ID and club_id != GLOBAL_CLUB_ID:
            return jsonify(success=False, message="Cannot delete a Global session type. You can create a local override instead."), 403

        if session_type and (session_type.club_id == club_id or club_id == GLOBAL_CLUB_ID):
            # Check if used in SessionLogs
            from .models import SessionLog
            usage_count = SessionLog.query.filter_by(Type_ID=id).count()
            if usage_count > 0:
                return jsonify(success=False, message=f"Cannot delete session type '{session_type.Title}' because it is in use by {usage_count} session log(s). Please reassign or delete the logs first."), 400
            
            db.session.delete(session_type)
            db.session.commit()
            return jsonify(success=True, message="Session type deleted successfully.")
        else:
            return jsonify(success=False, message="Session type not found or permission denied"), 404
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/roles/add', methods=['POST'])
@login_required
def add_role():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    club_id = get_current_club_id()
    
    # Check if role name already exists in this club
    trimmed_name = request.form.get('name', '').strip()
    if MeetingRole.query.filter_by(name=trimmed_name, club_id=club_id).first():
        flash(f'Role with name "{trimmed_name}" already exists in this club.', 'danger')
        return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))

    try:
        new_role = MeetingRole(
            name=trimmed_name,
            icon=request.form.get('icon'),
            type=request.form.get('type'),
            award_category=request.form.get('award_category'),
            needs_approval='needs_approval' in request.form,
            has_single_owner='has_single_owner' in request.form,
            is_member_only='is_member_only' in request.form,
            club_id=club_id
        )
        db.session.add(new_role)
        db.session.commit()
        flash('Role added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))


@settings_bp.route('/settings/roles/update', methods=['POST'])
@login_required
def update_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    club_id = get_current_club_id()
    try:
        for item in data:
            role = db.session.get(MeetingRole, item['id'])
            if role and role.club_id == club_id:
                role.name = item.get('name')
                role.icon = item.get('icon')
                role.type = item.get('type')
                role.award_category = item.get('award_category')
                role.needs_approval = item.get('needs_approval', False)
                role.has_single_owner = item.get('has_single_owner', False)
                role.is_member_only = item.get('is_member_only', False)

        db.session.commit()
        return jsonify(success=True, message="Roles updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/roles/delete/<int:id>', methods=['POST'])
@login_required
def delete_role(id):
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    club_id = get_current_club_id()
    try:
        role = db.session.get(MeetingRole, id)
        
        if role.club_id == GLOBAL_CLUB_ID and club_id != GLOBAL_CLUB_ID:
             return jsonify(success=False, message="Cannot delete a Global role."), 403

        if role and (role.club_id == club_id or club_id == GLOBAL_CLUB_ID):
            db.session.delete(role)
            db.session.commit()
            return jsonify(success=True, message="Role deleted successfully.")
        else:
            return jsonify(success=False, message="Role not found or permission denied"), 404
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/roles/import', methods=['POST'])
@login_required
def import_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))

    if file and file.filename.endswith('.csv'):
        try:
            # Read the file in-memory using utf-8-sig to handle BOM
            stream = io.StringIO(
                file.stream.read().decode("utf-8-sig"), newline=None)
            reader = csv.DictReader(stream)

            club_id = get_current_club_id()
             
            # Pre-fetch Global Roles for duplicate checking
            global_roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
            global_role_names = {r.name for r in global_roles}

            for row in reader:
                role_name = row.get('name')
                role_type = row.get('type')
                
                # Rule 1: If type is 'standard' and it exists in Global list, SKIP it.
                # This assumes we want to use the Global definition, not a local copy.
                if role_type == 'standard' and role_name in global_role_names:
                    continue

                # Check if it already exists LOCALLY
                if role_name and not MeetingRole.query.filter_by(name=role_name, club_id=club_id).first():
                    
                    # Rule 2: Force type to 'club-specific' for all imported roles
                    # (Unless it's the Global Club itself importing? The requirement didn't specify exception)
                    # "for all roles imported, set their types to 'club specific'"
                    # If I am Club 1 Admin importing, maybe I WANT standard?
                    # The request context likely implies "Normal Club importing from a list".
                    # But to be safe, if club_id == GLOBAL_CLUB_ID, we might want to respect CSV?
                    # User request: "while importing data... set their types to 'club specific'".
                    # I will apply this to non-global clubs.
                    
                    final_type = 'club-specific'
                    if club_id == GLOBAL_CLUB_ID:
                        final_type = role_type # Respect CSV for Global Club
                    
                    new_role = MeetingRole(
                        name=role_name,
                        icon=row.get('icon'),
                        type=final_type,
                        award_category=row.get('award_category'),
                        needs_approval=row.get(
                            'needs_approval', '0').strip() == '1',
                        has_single_owner=row.get('has_single_owner', '0').strip() == '1',
                        is_member_only=row.get('is_member_only', '0').strip() == '1',
                        club_id=club_id
                    )
                    db.session.add(new_role)

            db.session.commit()
            flash('Roles have been successfully imported.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')
    else:
        flash('Invalid file format. Please upload a .csv file.', 'danger')

    return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))







@settings_bp.route('/api/permissions/matrix', methods=['GET'])
@login_required
def get_permissions_matrix():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    # Exclude SysAdmin and ClubAdmin from the permissions matrix
    roles = AuthRole.query.filter(
        AuthRole.name.notin_(['SysAdmin', 'ClubAdmin'])
    ).order_by(AuthRole.id).all()
    permissions = Permission.query.order_by(Permission.category, Permission.name).all()
    
    # Get current mappings
    mappings = RolePermission.query.all()
    role_perms = {} # role_id -> [perm_id, ...]
    for m in mappings:
        if m.role_id not in role_perms:
            role_perms[m.role_id] = []
        role_perms[m.role_id].append(m.permission_id)

    return jsonify({
        'roles': [{'id': r.id, 'name': r.name} for r in roles],
        'permissions': [{
            'id': p.id, 
            'name': p.name, 
            'category': p.category, 
            'resource': p.resource,
            'description': p.description
        } for p in permissions],
        'role_perms': role_perms
    })

@settings_bp.route('/api/permissions/update', methods=['POST'])
@login_required
def update_permission_matrix():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        # data should be list of {role_id: X, permission_ids: [Y, Z]}
        for item in data:
            role_id = item.get('role_id')
            new_perm_ids = set(item.get('permission_ids', []))
            
            role = db.session.get(AuthRole, role_id)
            if not role:
                continue

            # Get current perms
            current_perms = RolePermission.query.filter_by(role_id=role_id).all()
            current_perm_ids = {p.permission_id for p in current_perms}

            # To add
            for pid in new_perm_ids - current_perm_ids:
                db.session.add(RolePermission(role_id=role_id, permission_id=pid))

            # To remove
            for p in current_perms:
                if p.permission_id not in new_perm_ids:
                    db.session.delete(p)
            
            # Audit log
            audit = PermissionAudit(
                admin_id=current_user.id,
                action='UPDATE_ROLE_PERMS',
                target_type='ROLE',
                target_id=role_id,
                target_name=role.name,
                changes=f"Updated permissions: {list(new_perm_ids)}"
            )
            db.session.add(audit)

        db.session.commit()
        return jsonify(success=True, message="Permissions updated successfully")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@settings_bp.route('/api/audit-log', methods=['GET'])
@login_required
def get_audit_log():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    logs = PermissionAudit.query.order_by(PermissionAudit.timestamp.desc()).limit(100).all()
    return jsonify([l.to_dict() for l in logs])

@settings_bp.route('/api/user-roles/update', methods=['POST'])
@login_required
def update_user_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json() # {user_id: X, role_ids: [Y, Z]}
    user_id = data.get('user_id')
    new_role_ids = set(data.get('role_ids', []))

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify(success=False, message="User not found"), 404

        # Calculate bitmask sum of all selected roles
        role_level = 0
        if new_role_ids:
            roles = AuthRole.query.filter(AuthRole.id.in_(new_role_ids)).all()
            for r in roles:
                role_level += r.level if r.level is not None else 0
        
        # Update all user's club memberships with the new role level
        user_clubs = UserClub.query.filter_by(user_id=user_id).all()
        
        if not user_clubs:
            # If user has no club memberships, create one for the current or default club
            club_id = get_current_club_id()
            if not club_id:
                default_club = Club.query.first()
                club_id = default_club.id if default_club else None
            
            if club_id:
                # Try to reuse an existing contact_id from another club membership
                existing_uc = UserClub.query.filter_by(user_id=user_id).first()
                contact_id = existing_uc.contact_id if existing_uc else None
                
                # Create a new UserClub entry
                uc = UserClub(
                    user_id=user.id,
                    club_id=club_id,
                    club_role_level=role_level,
                    contact_id=contact_id
                )
                db.session.add(uc)
        else:
            # Update role level for all existing club memberships
            for uc in user_clubs:
                if uc.club_role_level != role_level:
                    uc.club_role_level = role_level

        # Audit log
        audit = PermissionAudit(
            admin_id=current_user.id,
            action='UPDATE_USER_ROLES',
            target_type='USER',
            target_id=user_id,
            target_name=user.username,
            changes=f"Updated role level to: {role_level}"
        )
        db.session.add(audit)

        db.session.commit()
        return jsonify(success=True, message="User roles updated successfully")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
