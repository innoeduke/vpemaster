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
    roles = [{'id': role.id, 'name': role.name, 'award_category': role.award_category, 'type': role.type} for role in merged_roles]
    
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

    # Get current club context
    club_id = get_current_club_id()
        
    try:
        # Check if we are updating or adding
        session_id = request.form.get('id')
        session_type = None
        if session_id:
            session_type = db.session.get(SessionType, session_id)
            if not session_type or session_type.club_id != club_id:
                 return jsonify(success=False, message="Session type not found or permission denied"), 404

        # Check if title already exists in this club (excluding ourselves if updating)
        query = SessionType.query.filter_by(Title=title, club_id=club_id)
        if session_type:
            query = query.filter(SessionType.id != session_type.id)
        
        if query.first():
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
            if duration_min < 0 or duration_min > 480:  # 8-hour limit, allow 0
                return jsonify(success=False, message="Duration min must be between 0 and 480 minutes"), 400

        if duration_max_str:
            if not duration_max_str.isdigit():
                return jsonify(success=False, message="Duration max must be a positive integer"), 400
            duration_max = int(duration_max_str)
            if duration_max < 0 or duration_max > 480:
                return jsonify(success=False, message="Duration max must be between 0 and 480 minutes"), 400

        # Validate duration logic
        if duration_min is not None and duration_max is not None and duration_min > duration_max:
            return jsonify(success=False, message="Duration min cannot be greater than duration max"), 400

        role_id_str = request.form.get('role_id', '').strip()
        role_id = int(role_id_str) if role_id_str else None

        if session_type:
            # Update existing
            session_type.Title = title
            session_type.role_id = role_id
            session_type.Duration_Min = duration_min
            session_type.Duration_Max = duration_max
            session_type.Is_Section = 'is_section' in request.form
            session_type.Valid_for_Project = 'valid_for_project' in request.form
            session_type.Is_Hidden = 'is_hidden' in request.form
            msg = "Session type updated successfully"
        else:
            # Create new
            session_type = SessionType(
                Title=title,
                role_id=role_id,
                Duration_Min=duration_min,
                Duration_Max=duration_max,
                Is_Section='is_section' in request.form,
                Valid_for_Project='valid_for_project' in request.form,
                Is_Hidden='is_hidden' in request.form,
                club_id=club_id
            )
            db.session.add(session_type)
            msg = "Session type added successfully"

        db.session.commit()

        # Return the session object so the frontend can add/update it in the table
        session_data = {
            'id': session_type.id,
            'Title': session_type.Title,
            'role_id': session_type.role_id,
            'Duration_Min': session_type.Duration_Min,
            'Duration_Max': session_type.Duration_Max,
            'Is_Section': session_type.Is_Section,
            'Valid_for_Project': session_type.Valid_for_Project,
            'Is_Hidden': session_type.Is_Hidden
        }
        return jsonify(success=True, message=msg, new_session=session_data)

    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f"Value error processing session type: {str(e)}")
        return jsonify(success=False, message="Invalid input data"), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing session type: {str(e)}")
        return jsonify(success=False, message="Internal server error"), 500



@settings_bp.route('/settings/sessions/update', methods=['POST'])
@login_required
def update_session_types():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403
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
        return jsonify(success=False, message="Permission denied"), 403
    club_id = get_current_club_id()
    trimmed_name = request.form.get('name', '').strip()
    if not trimmed_name:
         return jsonify(success=False, message="Role name is required"), 400

    # Check if we are updating or adding
    role_id = request.form.get('id')
    role = None
    if role_id:
        role = db.session.get(MeetingRole, role_id)
        if not role or role.club_id != club_id:
            return jsonify(success=False, message="Role not found or permission denied"), 404

    # Check if role name already exists in this club
    query = MeetingRole.query.filter_by(name=trimmed_name, club_id=club_id)
    if role:
        query = query.filter(MeetingRole.id != role.id)
    
    if query.first():
        return jsonify(success=False, message=f'Role with name "{trimmed_name}" already exists in this club.'), 400

    try:
        if role:
            # Update existing
            role.name = trimmed_name
            role.icon = request.form.get('icon')
            role.type = request.form.get('type')
            role.award_category = request.form.get('award_category')
            role.needs_approval = 'needs_approval' in request.form
            role.has_single_owner = 'has_single_owner' in request.form
            role.is_member_only = 'is_member_only' in request.form
            msg = "Role updated successfully"
        else:
            # Create new
            role = MeetingRole(
                name=trimmed_name,
                icon=request.form.get('icon'),
                type=request.form.get('type'),
                award_category=request.form.get('award_category'),
                needs_approval='needs_approval' in request.form,
                has_single_owner='has_single_owner' in request.form,
                is_member_only='is_member_only' in request.form,
                club_id=club_id
            )
            db.session.add(role)
            msg = "Role added successfully"
        
        db.session.commit()

        # Return the role object so the frontend can add/update it in the table
        role_data = {
            'id': role.id,
            'name': role.name,
            'icon': role.icon,
            'type': role.type,
            'award_category': role.award_category,
            'needs_approval': role.needs_approval,
            'has_single_owner': role.has_single_owner,
            'is_member_only': role.is_member_only
        }
        return jsonify(success=True, message=msg, new_role=role_data)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing role: {str(e)}")
        return jsonify(success=False, message=f'An error occurred: {e}'), 500



@settings_bp.route('/settings/roles/update', methods=['POST'])
@login_required
def update_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403
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
        
        if not role:
             return jsonify(success=False, message="Role not found"), 404

        if role.club_id == GLOBAL_CLUB_ID and club_id != GLOBAL_CLUB_ID:
             return jsonify(success=False, message="Cannot delete a Global role."), 403

        if role and (role.club_id == club_id or club_id == GLOBAL_CLUB_ID):
            # Check usage in OwnerMeetingRoles (Meeting Assignments)
            from .models import OwnerMeetingRoles, SessionType
            from .models.roster import RosterRole
            
            usage_omr = OwnerMeetingRoles.query.filter_by(role_id=id).count()
            if usage_omr > 0:
                return jsonify(success=False, message=f"Cannot delete role '{role.name}' because it is assigned to {usage_omr} meeting(s). Please unassign it first."), 400

            # Check usage in SessionTypes
            usage_st = SessionType.query.filter_by(role_id=id).count()
            if usage_st > 0:
                return jsonify(success=False, message=f"Cannot delete role '{role.name}' because it is used by {usage_st} session type(s). Please update the session types first."), 400

            # Check usage in Roster
            usage_roster = RosterRole.query.filter_by(role_id=id).count()
            if usage_roster > 0:
                return jsonify(success=False, message=f"Cannot delete role '{role.name}' because it is used in {usage_roster} roster entry/entries. Please clear the rosters first."), 400

            db.session.delete(role)
            db.session.commit()
            return jsonify(success=True, message="Role deleted successfully.")
        else:
            return jsonify(success=False, message="Permission denied"), 403
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@settings_bp.route('/settings/roles/import', methods=['POST'])
@login_required
def import_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403
    club_id = get_current_club_id()

    if 'file' not in request.files:
        return jsonify(success=False, message="No file part"), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(success=False, message="No selected file"), 400

    if not file.filename.endswith('.csv'):
        return jsonify(success=False, message="File must be a CSV"), 400

    try:
        # Read CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        
        # Prepare data for DataImportService
        # Expected Schema: id, Name, Icon, Type, AwardCategory, needs_approval, has_single_owner, is_member_only
        # We generate dummy IDs for the list.
        roles_data = []
        dummy_id = 0
        for row in reader:
            dummy_id += 1
            # Map CSV columns to Service Schema
            # Default fallbacks handled here
            name = row.get('name', '').strip()
            if not name: continue
            
            icon = row.get('icon', 'fa-question')
            # Force all imported roles to be 'club-specific' if they are created locally.
            # DataImportService will still link to Global if a name match is found (ignoring this type).
            # But if no match is found, this ensures the new local role is created validly.
            rtype = 'club-specific'
            award = row.get('award_category', 'other')
            needs_app = row.get('needs_approval', 'false').lower() == 'true'
            single_own = row.get('has_single_owner', 'false').lower() == 'true'
            mem_only = row.get('is_member_only', 'false').lower() == 'true'
            
            roles_data.append((
                dummy_id,
                name,
                icon,
                rtype,
                award,
                needs_app,
                single_own,
                mem_only
            ))
            
        current_club_id = get_current_club_id()
        club = db.session.get(Club, current_club_id)
        
        from .services.data_import_service import DataImportService
        service = DataImportService(club.club_no)
        service.resolve_club() # Should resolve to current_club_id
        
        # Override club_id just to be safe (if club_no logic is tricky in Service)
        service.club_id = current_club_id
        
        service.import_meeting_roles(roles_data)
        
        db.session.commit()
        return jsonify(success=True, message=f"Imported {len(roles_data)} roles successfully (duplicates skipped).")

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500








@settings_bp.route('/api/permissions/matrix', methods=['GET'])
@login_required
def get_permissions_matrix():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403
    # club_id is implicitly used by is_authorized but if needed:
    # club_id = get_current_club_id()

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
    # club_id = get_current_club_id()

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
    # club_id = get_current_club_id()

    logs = PermissionAudit.query.order_by(PermissionAudit.timestamp.desc()).limit(100).all()
    return jsonify([l.to_dict() for l in logs])

@settings_bp.route('/api/user-roles/update', methods=['POST'])
@login_required
def update_user_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403
    # club_id = get_current_club_id()

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
