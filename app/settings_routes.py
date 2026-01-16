# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app, flash
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user
from .club_context import get_current_club_id, authorized_club_required
from .models import SessionType, User, LevelRole, MeetingRole, Achievement, Contact, Permission, AuthRole, RolePermission, UserRoleAssociation, PermissionAudit, ContactClub, Club, ExComm
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

    session_types = SessionType.query.order_by(SessionType.id.asc()).all()
    level_roles = LevelRole.query.order_by(
        LevelRole.level.asc(), LevelRole.type.desc()).all()
    all_users = User.query.order_by(User.Username.asc()).all()
    roles_query = MeetingRole.query.order_by(MeetingRole.name.asc()).all()
    roles = [{'id': role.id, 'name': role.name} for role in roles_query]
    
    # Achievements data
    achievements = Achievement.query.join(Contact).order_by(Achievement.issue_date.desc()).all()

    return render_template('settings.html', session_types=session_types, all_users=all_users, 
                          level_roles=level_roles, roles=roles, roles_query=roles_query, 
                          achievements=achievements)


@settings_bp.route('/about_club')
@login_required
@authorized_club_required
def about_club():
    """Renders the About Club page."""
    if not is_authorized(Permissions.ABOUT_CLUB_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    from .models import Club, ExComm
    
    # Get club from database using current context
    club_id = get_current_club_id()
    club = db.session.get(Club, club_id) if club_id else Club.query.first()
    
    # Get current excomm team from database
    excomm = None
    excomm_team = {
        'name': '', 
        'term': '', 
        'members': {
            'President': '', 'VPE': '', 'VPM': '', 'VPPR': '', 
            'Secretary': '', 'Treasurer': '', 'SAA': '', 'IPP': ''
        }
    }
    
    if club and club.current_excomm_id:
        excomm = ExComm.query.get(club.current_excomm_id)
        if excomm:
            excomm_team = {
                'name': excomm.excomm_name or '',
                'term': excomm.excomm_term or '',
                'members': {
                    'President': excomm.president.Name if excomm.president else '',
                    'VPE': excomm.vpe.Name if excomm.vpe else '',
                    'VPM': excomm.vpm.Name if excomm.vpm else '',
                    'VPPR': excomm.vppr.Name if excomm.vppr else '',
                    'Secretary': excomm.secretary.Name if excomm.secretary else '',
                    'Treasurer': excomm.treasurer.Name if excomm.treasurer else '',
                    'SAA': excomm.saa.Name if excomm.saa else '',
                    'IPP': excomm.ipp.Name if excomm.ipp else ''
                }
            }

    # Get all member contacts for ExComm officer selection, filtered by club
    all_contacts = Contact.query.join(ContactClub).filter(
        ContactClub.club_id == (club.id if club else None),
        Contact.Type == 'Member'
    ).order_by(Contact.Name.asc()).all()
    contacts_list = [{'id': c.id, 'name': c.Name} for c in all_contacts]

    return render_template('about_club.html', club=club, excomm_team=excomm_team, contacts_list=contacts_list)


@settings_bp.route('/about_club/update', methods=['POST'])
@login_required
@authorized_club_required
def about_club_update():
    """Update club settings from the about club page."""
    if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
        return jsonify(success=False, message="Permission denied"), 403
    
    from .models import Club, ExComm, Contact
    
    try:
        data = request.get_json()
        
        # Get the club from current context
        club_id = get_current_club_id()
        club = db.session.get(Club, club_id)
        if not club:
            return jsonify(success=False, message="No club found"), 404
            
        # Update club fields
        if 'club_no' in data:
            club.club_no = data['club_no']
        if 'club_name' in data:
            club.club_name = data['club_name']
        if 'short_name' in data:
            club.short_name = data['short_name'] or None
        if 'district' in data:
            club.district = data['district'] or None
        if 'division' in data:
            club.division = data['division'] or None
        if 'area' in data:
            club.area = data['area'] or None
        if 'club_address' in data:
            club.club_address = data['club_address'] or None
        if 'meeting_date' in data:
            club.meeting_date = data['meeting_date'] or None
        if 'contact_phone_number' in data:
            club.contact_phone_number = data['contact_phone_number'] or None
        if 'website' in data:
            website = data['website'] or None
            if website and not (website.startswith('http://') or website.startswith('https://')):
                website = 'https://' + website
            club.website = website
        
        # Parse meeting time
        if 'meeting_time' in data and data['meeting_time']:
            try:
                club.meeting_time = datetime.strptime(data['meeting_time'], '%H:%M').time()
            except ValueError:
                return jsonify(success=False, message="Invalid meeting time format"), 400
        
        # Parse founded date
        if 'founded_date' in data and data['founded_date']:
            try:
                club.founded_date = datetime.strptime(data['founded_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify(success=False, message="Invalid founded date format"), 400

        # Update ExComm fields
        excomm = None
        if club.current_excomm_id:
            excomm = ExComm.query.get(club.current_excomm_id)
            
        # Check if we have ANY ExComm-related data
        excomm_fields = ['excomm_name', 'excomm_term', 'excomm_president', 'excomm_vpe', 
                         'excomm_vpm', 'excomm_vppr', 'excomm_secretary', 'excomm_treasurer', 
                         'excomm_saa', 'excomm_ipp']
        has_excomm_data = any(field in data for field in excomm_fields)

        if has_excomm_data:
            if not excomm:
                # Create a new ExComm record if none exists
                # Determine a default term if not provided (e.g., current year + H1/H2)
                now = datetime.now()
                default_term = f"{now.year % 100}{'H1' if now.month <= 6 else 'H2'}"
                
                excomm = ExComm(
                    club_id=club.id,
                    excomm_term=data.get('excomm_term') or default_term
                )
                db.session.add(excomm)
                db.session.flush() # Get ID
                club.current_excomm_id = excomm.id
            
            if 'excomm_name' in data:
                excomm.excomm_name = data['excomm_name'] or None
            if 'excomm_term' in data and data['excomm_term']:
                excomm.excomm_term = data['excomm_term']

            # Update ExComm Officers
            officer_roles = {
                'excomm_president': 'president_id',
                'excomm_vpe': 'vpe_id',
                'excomm_vpm': 'vpm_id',
                'excomm_vppr': 'vppr_id',
                'excomm_secretary': 'secretary_id',
                'excomm_treasurer': 'treasurer_id',
                'excomm_saa': 'saa_id',
                'excomm_ipp': 'ipp_id'
            }

            for field, model_attr in officer_roles.items():
                if field in data:
                    officer_name = data[field]
                    if not officer_name:
                        setattr(excomm, model_attr, None)
                    else:
                        contact = Contact.query.filter_by(Name=officer_name).first()
                        if contact:
                            setattr(excomm, model_attr, contact.id)
                        else:
                            # If contact not found, maybe ignore or set to None
                            setattr(excomm, model_attr, None)

        club.updated_at = datetime.utcnow()
        if excomm:
            excomm.updated_at = datetime.utcnow()
            
        db.session.commit()
        
        return jsonify(success=True, message="Settings updated successfully")
    
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500



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

        # Check if title already exists
        existing_session = SessionType.query.filter_by(Title=title).first()
        if existing_session:
            return jsonify(success=False, message="Session type with this title already exists"), 400

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
            Default_Owner=request.form.get(
                'default_owner', '').strip() or None,
            role_id=role_id,
            Duration_Min=duration_min,
            Duration_Max=duration_max,
            Is_Section='is_section' in request.form,
            Predefined='predefined' in request.form,
            Valid_for_Project='valid_for_project' in request.form,
            Is_Hidden='is_hidden' in request.form
        )
        db.session.add(new_session)
        db.session.commit()

        # Return the new session object so the frontend can add it to the table
        new_session_data = {
            'id': new_session.id,
            'Title': new_session.Title,
            'Default_Owner': new_session.Default_Owner,
            'role_id': new_session.role_id,
            'Duration_Min': new_session.Duration_Min,
            'Duration_Max': new_session.Duration_Max,
            'Is_Section': new_session.Is_Section,
            'Predefined': new_session.Predefined,
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

    try:
        for item in data:
            session_type = db.session.get(SessionType, item['id'])
            if session_type:
                session_type.Title = item.get('Title')
                session_type.Default_Owner = item.get('Default_Owner')
                role_id_str = item.get('role_id')
                session_type.role_id = int(
                    role_id_str) if role_id_str else None
                session_type.Is_Section = item.get('Is_Section', False)
                session_type.Predefined = item.get('Predefined', False)
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


@settings_bp.route('/settings/roles/add', methods=['POST'])
@login_required
def add_role():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_role = MeetingRole(
            name=request.form.get('name'),
            icon=request.form.get('icon'),
            type=request.form.get('type'),
            award_category=request.form.get('award_category'),
            needs_approval='needs_approval' in request.form,
            is_distinct='is_distinct' in request.form,
            is_member_only='is_member_only' in request.form
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

    try:
        for item in data:
            role = db.session.get(MeetingRole, item['id'])
            if role:
                role.name = item.get('name')
                role.icon = item.get('icon')
                role.type = item.get('type')
                role.award_category = item.get('award_category')
                role.needs_approval = item.get('needs_approval', False)
                role.is_distinct = item.get('is_distinct', False)
                role.is_member_only = item.get('is_member_only', False)

        db.session.commit()
        return jsonify(success=True, message="Roles updated successfully.")
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

            for row in reader:
                role_name = row.get('name')
                if role_name and not MeetingRole.query.filter_by(name=role_name).first():
                    new_role = MeetingRole(
                        name=role_name,
                        icon=row.get('icon'),
                        type=row.get('type'),
                        award_category=row.get('award_category'),
                        needs_approval=row.get(
                            'needs_approval', '0').strip() == '1',
                        is_distinct=row.get('is_distinct', '0').strip() == '1',
                        is_member_only=row.get('is_member_only', '0').strip() == '1'
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


@settings_bp.route('/settings/level-roles/add', methods=['POST'])
@login_required
def add_level_role():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_role = LevelRole(
            level=int(request.form.get('level')),
            role=request.form.get('role'),
            type=request.form.get('type'),
            count_required=int(request.form.get('count_required')) if request.form.get(
                'count_required') else 0
        )
        db.session.add(new_role)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    return redirect(url_for('settings_bp.settings', default_tab='level-roles'))


@settings_bp.route('/settings/level-roles/update', methods=['POST'])
@login_required
def update_level_roles():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            level_role = db.session.get(LevelRole, item['id'])
            if level_role:
                level_role.level = int(
                    item.get('level')) if item.get('level') else None
                level_role.role = item.get('role')
                level_role.type = item.get('type')
                level_role.count_required = int(
                    item.get('count_required')) if item.get('count_required') else 0

        db.session.commit()
        return jsonify(success=True, message="Level roles updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500




@settings_bp.route('/api/permissions/matrix', methods=['GET'])
@login_required
def get_permissions_matrix():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    roles = AuthRole.query.order_by(AuthRole.id).all()
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

        current_roles = UserRoleAssociation.query.filter_by(user_id=user_id).all()
        current_role_ids = {r.role_id for r in current_roles}

        # To add
        for rid in new_role_ids - current_role_ids:
            db.session.add(UserRoleAssociation(
                user_id=user_id, 
                role_id=rid,
                assigned_by=current_user.id
            ))

        # To remove
        for r in current_roles:
            if r.role_id not in new_role_ids:
                db.session.delete(r)

        # Audit log
        audit = PermissionAudit(
            admin_id=current_user.id,
            action='UPDATE_USER_ROLES',
            target_type='USER',
            target_id=user_id,
            target_name=user.Username,
            changes=f"Updated roles: {list(new_role_ids)}"
        )
        db.session.add(audit)

        db.session.commit()
        return jsonify(success=True, message="User roles updated successfully")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
