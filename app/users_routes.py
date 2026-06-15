from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify, abort
from . import db
from .models import User, Contact, Pathway, Message
from .auth.utils import is_authorized, login_required
from .auth.permissions import Permissions
from flask_login import current_user

from werkzeug.security import generate_password_hash
from datetime import date
from sqlalchemy import or_
import csv
import io
from .club_context import get_current_club_id
from .constants import GLOBAL_CLUB_ID

users_bp = Blueprint('users_bp', __name__)


def _save_user_data(user=None, **kwargs):
    """
    Orchestrates user creation/updating.
    Separates business logic (roles, audit) from data logic (model).
    """
    from .models import AuthRole, PermissionAudit, Club, Contact
    from .club_context import get_current_club_id
    import re

    # Username syntax: letters, digits, underscores only.
    if kwargs.get('username') and not re.fullmatch(r'[A-Za-z0-9_]+', kwargs['username']):
        raise ValueError("Username may contain only letters, digits, and underscores.")

    # 1. Create or Update User instance
    is_new = user is None
    is_sysadmin = is_authorized(Permissions.SYSADMIN)
    # Username can only be changed by a sysadmin viewing the super club.
    # A regular clubadmin in their own club has ROSTER_EDIT but not
    # SYSADMIN, so this gates username edits to the super-club sysadmin.
    is_super_club_sysadmin = is_sysadmin and get_current_club_id() == GLOBAL_CLUB_ID
    if is_new:
        user = User(
            username=kwargs.get('username'),
            created_at=date.today(),
            status='active'
        )
        password = kwargs.get('password') or 'toastmasters'
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    else:
        # Existing User
        # Calculate permissions
        is_home_club_admin = False
        if current_user.is_authenticated and user.home_club:
            is_home_club_admin = current_user.has_club_permission(Permissions.SETTINGS_EDIT, user.home_club.id)

        if is_super_club_sysadmin:
            if kwargs.get('username'):
                user.username = kwargs.get('username')
            if kwargs.get('status'):
                user.status = kwargs.get('status')
        
        # Password update allowed for SysAdmin OR Home Club Admin
        if is_sysadmin or is_home_club_admin:
            password = kwargs.get('password')
            if password:
                user.set_password(password)
    
    # Update names - Only if NEW or current_user is SysAdmin
    if is_new or is_sysadmin:
        if kwargs.get('first_name'):
            user.first_name = kwargs.get('first_name')
        if kwargs.get('last_name'):
            user.last_name = kwargs.get('last_name')

        # Update other fields
        user.phone = kwargs.get('phone')
        email = kwargs.get('email')
        if email:
            email = email.strip()
            existing_email_user = User.query.filter_by(email=email).first()
            if existing_email_user and existing_email_user.id != user.id:
                raise ValueError("Email address is already registered.")
            user.email = email
        else:
            user.email = None


    # Link existing contact if provided
    contact_id = kwargs.get('contact_id')
    create_new_contact = kwargs.get('create_new_contact')
    club_id = kwargs.get('club_id') or get_current_club_id()
    
    # 1. User selected an existing contact to link
    if contact_id and contact_id != 0 and not create_new_contact:
        # Verify contact exists AND strictly belongs to the target club to prevent cross-club leakage
        # Check if contact exists AND strictly belongs to the target club to prevent cross-club leakage
        from .models import ContactClub
        is_in_club = ContactClub.query.filter_by(contact_id=contact_id, club_id=club_id).first()
        if is_in_club:
            contact = db.session.get(Contact, contact_id)
            if contact:
                # Ensure UserClub linkage
                from .models import UserClub
                uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
                if uc:
                    uc.contact_id = contact_id
                else:
                    db.session.add(UserClub(user_id=user.id, club_id=club_id, contact_id=contact_id))

                # Mirror the contact's avatar onto the User record. The User
                # owns its own profile photo; if the user later customises it
                # via "Change Photo", that wins and we don't overwrite on
                # subsequent contact re-links.
                if not user.avatar_url and contact.Avatar_URL:
                    user.avatar_url = contact.Avatar_URL

    # 2. Handle Contact (Delegated to Model or ensure existing)
    user.ensure_contact(
        full_name=kwargs.get('full_name'),
        first_name=kwargs.get('first_name') or user.first_name,
        last_name=kwargs.get('last_name') or user.last_name,
        email=user.email,
        phone=user.phone,
        club_id=club_id
    )

    # 3. Handle Roles
    # Logic: Assign single role_id (FK to auth_roles) to CURRENT club
    role_id = kwargs.get('role_id')
    if role_id is None and is_new:
        from .models import AuthRole
        user_role = AuthRole.query.filter_by(name='Member').first()
        role_id = user_role.id if user_role else None
        
    if role_id is not None:
        user.set_club_role(club_id, role_id=role_id)
        
        # 4. Audit Log
        if current_user and current_user.is_authenticated:
             audit = PermissionAudit(
                 admin_id=current_user.id,
                 action='UPDATE_USER_ROLES',
                 target_type='USER',
                 target_id=user.id,
                 target_name=user.username,
                 changes=f"Updated role to ID: {role_id}"
             )
             db.session.add(audit)
    
    return user



@users_bp.route('/users')
@login_required
def show_users():
    if not is_authorized(Permissions.MEMBERS_MANAGE):
        abort(403)

    from .models import AuthRole
    club_id = get_current_club_id()

    # Auth Roles for User Modal - SysAdmin is now account-based, so filter it out
    all_auth_roles_query = AuthRole.query.filter(
        (AuthRole.club_id == club_id) | (AuthRole.club_id.is_(None))
    ).order_by(AuthRole.level.desc()).all()
    all_auth_roles = [{'id': r.id, 'name': r.name, 'level': r.level} for r in all_auth_roles_query if r.name not in ('Guest', 'SysAdmin')]

    # Get Club name context
    club_name = None
    if club_id:
        from .models import Club
        club = db.session.get(Club, club_id)
        if club:
            club_name = club.club_name

    is_super_club_sysadmin = (
        current_user.is_authenticated
        and current_user.is_sysadmin
        and club_id == GLOBAL_CLUB_ID
    )

    # Server-render the first page so the user sees rows immediately.
    # The JS background-loads the rest of the rows for client pagination.
    # Local import to avoid circular import at module load time.
    from .settings_routes import _build_users_data, DEFAULT_USERS_PER_PAGE
    initial_users, users_total, _ = _build_users_data(
        per_page=DEFAULT_USERS_PER_PAGE, offset=0
    )
    if initial_users is None:
        initial_users = []
        users_total = 0

    # KPI: total members in the club. The stat must match the table below,
    # so it uses the same data source (users joined to UserClub, status
    # != 'deleted'). A Contact+ContactClub join can overcount because a
    # contact with Type='Member' can exist in the club without a backing
    # user account.
    type_counts = {'Member': users_total}

    return render_template('users.html',
                           club_id=club_id,
                           club_name=club_name,
                           all_auth_roles=all_auth_roles,
                           initial_users=initial_users,
                           users_total=users_total,
                           type_counts=type_counts,
                           is_super_club_sysadmin=is_super_club_sysadmin)


@users_bp.route('/user/form', defaults={'user_id': None}, methods=['GET', 'POST'])
@users_bp.route('/user/form/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_form(user_id):
    if not is_authorized(Permissions.MEMBERS_MANAGE):
        abort(403)

    from .models import AuthRole, UserClub

    user = None
    if user_id:
        user = db.get_or_404(User, user_id)
    
    club_id = request.args.get('club_id', type=int) or request.form.get('club_id', type=int) or get_current_club_id()
    target_role_name = request.args.get('role')
    
    source_contact = None
    contact_id = request.args.get('contact_id', type=int)
    if contact_id and not user:
        source_contact = db.session.get(Contact, contact_id)

    member_contacts = Contact.query.filter(
        Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    mentor_contacts = Contact.query.filter(or_(
        Contact.Type == 'Member', Contact.Type == 'Past Member')).order_by(Contact.Name.asc()).all()

    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    if request.method == 'POST':
        # Single role selection (radio button)
        role_id = request.form.get('role_id', type=int)
        
        # Security check: User role is standard, other roles (ClubAdmin, Staff) 
        # checked via standard permissions. SysAdmin role no longer exists in DB.
        
        try:
            _save_user_data(
                user=user,
                username=request.form.get('username'),
                full_name=request.form.get('full_name'),
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                role_id=role_id,
                status=request.form.get('status'),
                contact_id=request.form.get('contact_id', 0, type=int),
                create_new_contact=request.form.get('create_new_contact') == 'on',
                password=request.form.get('password'),
                club_id=club_id
            )
            db.session.commit()
            
            action = 'updated' if user else 'created'
            flash(f'User {request.form.get("username")} {action} successfully.', 'success')
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'error')
            return redirect(url_for('users_bp.user_form', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error saving user: {e}', exc_info=True)
            flash(f'Error saving user: {e}', 'error')
            return redirect(url_for('users_bp.user_form', user_id=user_id))

        return redirect(url_for('users_bp.show_users'))

    current_user_is_sysadmin = current_user.is_authenticated and current_user.is_sysadmin
    is_super_club_sysadmin = current_user_is_sysadmin and get_current_club_id() == GLOBAL_CLUB_ID
    all_auth_roles = AuthRole.query.filter(
        (AuthRole.club_id == club_id) | (AuthRole.club_id.is_(None))
    ).order_by(AuthRole.level.desc()).all()
    
    # Filter roles based on permissions
    filtered_roles = []
    for role in all_auth_roles:
        # User/ClubAdmin/Staff are standard. SysAdmin role is being removed.
        if role.name == 'SysAdmin':
            continue
        # Guest role should not be assignable in user management
        if role.name == 'Guest':
            continue
        filtered_roles.append(role)
    
    user_role_ids = []
    user_contact = None
    is_edit_self = False
    
    if user:
        is_edit_self = (user.id == current_user.id)
        # Fix: Only load roles/contact for the specific club context to prevent leakage
        from .models import UserClub
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
        if uc:
            if uc.auth_role:
                user_role_ids.append(uc.auth_role.id)
            user_contact = uc.contact
            
        if not user_contact and not source_contact:
            # Try to find ANY contact of this user to pre-populate (without linking ID yet)
            any_uc = UserClub.query.filter_by(user_id=user.id).first()
            if any_uc:
                source_contact = any_uc.contact
            
    if not user and target_role_name:
        target_role = AuthRole.query.filter_by(name=target_role_name).first()
        if target_role:
            user_role_ids.append(target_role.id)
            
    club_name = None
    if club_id:
        from .models import Club
        club = db.session.get(Club, club_id)
        if club:
            club_name = club.club_name

    # Check if current user is admin of the target user's home club
    is_home_club_admin = False
    can_reset_password = False
    
    if user:
        if current_user_is_sysadmin:
            is_home_club_admin = True
            can_reset_password = True
        elif user.home_club and current_user.has_club_permission(Permissions.SETTINGS_EDIT, user.home_club.id):
            is_home_club_admin = True
            # New Requirement: Disable password reset if home club is not the current club
            if user.home_club.id == club_id:
                can_reset_password = True
    else:
        # New user: Always allow password setting
        can_reset_password = True

    return render_template('user_form.html', user=user, user_contact=user_contact, source_contact=source_contact,
                           contacts=member_contacts, mentor_contacts=mentor_contacts, pathways=pathways,
                           all_auth_roles=filtered_roles, user_role_ids=user_role_ids,
                           club_id=club_id, club_name=club_name, is_edit_self=is_edit_self,
                           current_user_is_sysadmin=current_user_is_sysadmin,
                           is_super_club_sysadmin=is_super_club_sysadmin,
                           is_home_club_admin=is_home_club_admin,
                           can_reset_password=can_reset_password)


@users_bp.route('/user/check_duplicates', methods=['POST'])
@login_required
def check_duplicates():
    if not is_authorized(Permissions.MEMBERS_MANAGE):
        abort(403)
    """Checks for potential duplicate users or contacts."""
    data = request.json
    username = data.get('username', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    club_id = data.get('club_id') or get_current_club_id()
    
    duplicates = []
    
    # 1. Global User Search
    # Check for existing users across the ENTIRE system (no club restriction)
    user_query = User.query
    user_filters = []
    
    if username:
        user_filters.append(User.username == username)
    if email:
        user_filters.append(User.email == email)
    if phone:
        user_filters.append(User.phone == phone)
    
    # Name Search:
    # If first/last provided, match exactly.
    # Logic: OR (username match) OR (email match) OR (phone match) OR (Name Match)
    if first_name and last_name:
         user_filters.append(
             (User._first_name == first_name) & (User._last_name == last_name)
         )
    elif full_name:
         # Fallback if separate parts not available but full_name is (e.g. legacy/other entry points)
         # This is harder to query on User table directly if names are split.
         # For now, rely on first/last if possible.
         pass
    
    if user_filters:
        existing_users = User.query.filter(or_(*user_filters)).all()
        from .models import ContactClub
        
        # Batch populate contacts to avoid N+1 in the loop below
        User.populate_contacts(existing_users, club_id)
        
        for u in existing_users:
            in_current_club = False
            contact = u.get_contact(club_id) # Result depends on club_id context
            
            # Check if strictly a member of the target club
            # If u.contact exists for this club, then yes.
            if contact:
                 # Double check ContactClub specifically
                 in_current_club = ContactClub.query.filter_by(
                    contact_id=contact.id, 
                    club_id=club_id
                 ).first() is not None
            
            duplicates.append({
                'type': 'User',
                'id': u.id,
                'username': u.username,
                'full_name': u.display_name, # Use dynamic property
                'first_name': u.first_name,
                'last_name': u.last_name,
                'clubs': [uc.club.club_name for uc in u.club_memberships if uc.club] if u.club_memberships else [],
                'in_current_club': in_current_club
            })
            
    # 2. Local Contact Search (Fallback)
    # Only search contacts if they are NOT already linked to a user we found above
    # AND search specifically within the target club properties OR global properties?
    # User Request: "if not found, loop up local contacts table (target club only)."
    
    # If we found matches in User table, user said "if not found...". 
    # But usually we want to show ALL potential matches. 
    # Let's check for contacts in the CURRENT club that match.
    
    contact_filters = []
    if full_name:
        contact_filters.append(Contact.Name == full_name)
    if email:
        contact_filters.append(Contact.Email == email)
    if phone:
        contact_filters.append(Contact.Phone_Number == phone)
        
    if contact_filters:
        # Filter by Club Context FIRST to satisfy "local contacts table (target club only)"
        # We join with ContactClub to ensure they are in the target club
        from .models import ContactClub
        
        existing_contacts = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == club_id
        ).filter(or_(*contact_filters)).all()

        for c in existing_contacts:
            # Skip if this contact is already represented in our duplicates list (via its user)
            # Check if this contact is linked to any of the users we already found
            already_found_user_ids = [d['id'] for d in duplicates if d['type'] == 'User']
            if c.user and c.user.id in already_found_user_ids:
                continue
                
            # If contact has a user but that user wasn't found by the global search (e.g. name mismatch?),
            # we should still report it, but ideally as a User match.
            # However, for now, let's treat it as a Contact match but indicate it has a user.

            in_current_club = True # By definition of the query above
            
            duplicates.append({
                'type': 'Contact',
                'id': c.id,
                'user_id': c.user.id if c.user else None,
                'username': c.user.username if c.user else 'N/A',
                'full_name': c.Name,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'email': c.Email,
                'phone': c.Phone_Number,
                'clubs': [club.club_name for club in c.get_clubs()],
                'has_user': c.user is not None,
                'in_current_club': True
            })
            
    username_taken = any(d['username'].lower() == (username or '').lower() for d in duplicates if d.get('username') and d['username'] != 'N/A')
    suggested_username = None
    
    if username_taken:
        # Generate a suggestion
        base = username
        counter = 1
        while True:
            candidate = f"{base}{counter}"
            if not User.query.filter_by(username=candidate).first():
                suggested_username = candidate
                break
            counter += 1

    return {
        'duplicates': duplicates,
        'suggested_username': suggested_username
    }




@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not is_authorized(Permissions.MEMBERS_MANAGE):
        abort(403)

    from .constants import GLOBAL_CLUB_ID

    user = db.get_or_404(User, user_id)
    current_club_id = get_current_club_id()

    if user.id == current_user.id:
        from .translations.translations import translate as _
        msg = _("You cannot remove yourself from the club. Please contact another administrator or the system administrator for assistance.")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg)
        flash(msg, 'warning')
        return redirect(url_for('users_bp.show_users'))

    # Super club is a management interface, not a real club. "Remove from
    # the super club" therefore means "remove the user from the system":
    # delete the User row, which cascades to all UserClub rows via
    # User.club_memberships (cascade='all, delete-orphan'). The linked
    # Contact is a separate entity and is left intact — it may still be
    # referenced from other clubs.
    if current_club_id == GLOBAL_CLUB_ID:
        username = user.username
        try:
            counts = user.delete_with_dependents()
            db.session.commit()
            current_app.logger.info(
                f'Deleted user {user_id} ({username}) with dependents: {counts}'
            )
            flash(f'User {username} deleted from the system.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error deleting user {user_id}: {e}', exc_info=True)
            flash(f'Error deleting user: {e}', 'error')
        return redirect(url_for('users_bp.show_users'))

    # Regular club: delegate to the model. The User account is kept; only
    # the UserClub row goes away, and the linked Contact is demoted to Guest.
    try:
        user.remove_from_club(current_club_id)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error removing user {user_id} from club: {e}', exc_info=True)
        flash('An error occurred during removal.', 'error')

    return redirect(url_for('users_bp.show_users'))


@users_bp.route('/user/bulk_import', methods=['GET', 'POST'])
@login_required
def bulk_import_members():
    if not is_authorized(Permissions.MEMBERS_MANAGE):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('users_bp.show_users'))

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('users_bp.bulk_import_members'))

        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(url_for('users_bp.bulk_import_members'))

        if file and (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
            ext = file.filename.rsplit('.', 1)[1].lower()
            file_bytes = file.read()

            from app.services.member_import_service import process_member_file
            club_id = get_current_club_id()
            report = process_member_file(file_bytes, ext, club_id)

            added = report.get('added', [])
            invited = report.get('invited', [])
            failed_users = report.get('failed', [])

            show_example = any(
                "Failed to parse" in f or "Unsupported file extension" in f or "Invalid column headers" in f
                for f in failed_users
            )
            return render_template(
                'import_report.html',
                added=added,
                invited=invited,
                failed_users=failed_users,
                show_example=show_example,
                is_post=True
            )

        else:
            # If the file doesn't have .csv or .xlsx, or doesn't exist
            failed_users = ["Invalid file type. Please upload a .csv or .xlsx file."]
            return render_template(
                'import_report.html',
                added=[],
                invited=[],
                failed_users=failed_users,
                show_example=True,
                is_post=True
            )

    # GET request: render empty upload form
    return render_template(
        'import_report.html',
        added=[],
        invited=[],
        failed_users=[],
        show_example=True,
        is_post=False
    )


@users_bp.route('/user/request_join', methods=['POST'])
@login_required
def request_join():
    """Sends a join request to a user."""
    data = request.json
    target_user_id = data.get('target_user_id')
    club_id = data.get('club_id')

    if not target_user_id or not club_id:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
    target_user = db.session.get(User, target_user_id)
    if not target_user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    from .models import Club
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    # Check if already a member
    from .models import UserClub
    if UserClub.query.filter_by(user_id=target_user_id, club_id=club_id).first():
        return jsonify({'success': False, 'error': 'User is already a member'}), 400

    # If SysAdmin, add directly
    from .auth.utils import is_authorized
    from .auth.permissions import Permissions
    
    if is_authorized(Permissions.SYSADMIN):
        # Ensure contact and linkage exists
        target_user.ensure_contact(club_id=club_id)
        # Set default role (User/Member)
        from .models import AuthRole as AR
        default_role = AR.query.filter_by(name='Member').first()
        target_user.set_club_role(club_id, role_id=default_role.id if default_role else None)
        db.session.commit()
        return jsonify({'success': True, 'direct_add': True})

    # Create Message with special tag
    msg = Message(
        sender_id=current_user.id,
        recipient_id=target_user_id,
        subject=f"Invitation to join {club.club_name}",
        body=f"Hello {target_user.first_name},\n\n{current_user.display_name} has invited you to join **{club.club_name}**.\n\nPlease respond using the buttons below.\n[CLUB_ID:{club_id}]"
    )
    
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({'success': True})


@users_bp.route('/user/respond_join', methods=['POST'])
@login_required
def respond_join():
    """Handles response to a join request."""
    data = request.json
    message_id = data.get('message_id')
    action = data.get('action') # 'join' or 'reject'
    
    msg = db.session.get(Message, message_id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
        
    if msg.recipient_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    # Extract Club ID from body
    import re
    match = re.search(r'\[CLUB_ID:(\d+)\]', msg.body)
    if not match:
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400
        
    club_id = int(match.group(1))
    
    from .models import Club, UserClub
    club = db.session.get(Club, club_id)
    
    if action == 'join':
        # Add to club
        if not UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first():
            # Ensure contact and linkage exists
            current_user.ensure_contact(club_id=club_id)
            # Set default role (User/Member)
            from .models import AuthRole as AR2
            default_role2 = AR2.query.filter_by(name='Member').first()
            current_user.set_club_role(club_id, role_id=default_role2.id if default_role2 else None)
            
            response_body = f"{current_user.display_name} has accepted your request to join {club.club_name}."
        else:
             response_body = f"{current_user.display_name} is already a member of {club.club_name}."

    elif action == 'reject':
        response_body = f"{current_user.display_name} has declined to join {club.club_name}."
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

    # Notify Sender (Club Admin)
    reply = Message(
        sender_id=current_user.id,
        recipient_id=msg.sender_id,
        subject=f"Join Request Response: {club.club_name}",
        body=response_body
    )
    db.session.add(reply)
    
    # Update original message to remove buttons/tag
    msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: {action.upper()}]")
    msg.read = True
    
    db.session.commit()
    
    return jsonify({'success': True})
