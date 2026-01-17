from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from . import db
from .models import User, Contact, Pathway
from .auth.utils import is_authorized, login_required
from .auth.permissions import Permissions
from flask_login import current_user

from werkzeug.security import generate_password_hash
from datetime import date
from sqlalchemy import or_
import csv
import io

users_bp = Blueprint('users_bp', __name__)


def _create_or_update_user(user=None, **kwargs):
    """Helper function to create or update a user."""

    if user is None:
        # Creating a new user
        user = User(Date_Created=date.today())
        password = kwargs.get('password') or 'leadership'
        user.Pass_Hash = generate_password_hash(password, method='pbkdf2:sha256')
        user.Status = 'active'
        db.session.add(user)
    else:
        # Updating an existing user
        password = kwargs.get('password')
        if password:
            user.Pass_Hash = generate_password_hash(password, method='pbkdf2:sha256')
        user.Status = kwargs.get('status')

    user.Username = kwargs.get('username')
    # Set email to None if empty to avoid unique constraint violation
    email = kwargs.get('email')
    user.Email = email if email else None
    
    # Capture old contact ID for syncing
    old_contact_id = user.Contact_ID
    
    # Handle multiple roles - now stored in user_clubs table
    role_ids = kwargs.get('role_ids', [])
    role_name = kwargs.get('role') # Legacy single-role support
    from .models import UserClub, AuthRole, PermissionAudit, Club
    from flask_login import current_user
    from .club_context import get_current_club_id
    
    # If role_name is provided but role_ids is not, try to find the role
    if not role_ids and role_name:
        role_obj = AuthRole.query.filter_by(name=role_name).first()
        if role_obj:
            role_ids = [role_obj.id]
    
    # For new users, ensure they get at least the "User" role by default
    is_new_user = user.id is None
    if is_new_user and not role_ids:
        default_role = AuthRole.query.filter_by(name='User').first()
        if default_role:
            role_ids = [default_role.id]
    
    # Determine the highest role to assign
    highest_role_id = None
    if role_ids:
        roles = AuthRole.query.filter(AuthRole.id.in_(role_ids)).all()
        if roles:
            highest_role = max(roles, key=lambda r: r.level if r.level is not None else 0)
            highest_role_id = highest_role.id

    if user.id:
        # Update existing user's club memberships with new role
        if highest_role_id:
            user_clubs = UserClub.query.filter_by(user_id=user.id).all()
            
            # If user has no club memberships yet, create one for current or default club
            if not user_clubs:
                club_id = get_current_club_id()
                if not club_id:
                    default_club = Club.query.first()
                    club_id = default_club.id if default_club else None
                
                if club_id:
                    new_uc = UserClub(
                        user_id=user.id,
                        club_id=club_id,
                        club_role_id=highest_role_id
                    )
                    db.session.add(new_uc)
            else:
                # Update role for all existing club memberships
                for uc in user_clubs:
                    old_role_id = uc.club_role_id
                    uc.club_role_id = highest_role_id
                    
            # Audit log
            if current_user.is_authenticated:
                audit = PermissionAudit(
                    admin_id=current_user.id,
                    action='UPDATE_USER_ROLES',
                    target_type='USER',
                    target_id=user.id,
                    target_name=user.Username,
                    changes=f"Updated role to: {highest_role_id}"
                )
                db.session.add(audit)
    else:
        # For new users, we'll create a UserClub record after user is created
        # Store the role_id temporarily to use after flush
        user._pending_role_id = highest_role_id


    # Profile fields (Member_ID, Current_Path, etc.) are now on Contact model.
    # We do not set them here.

    # Always create a contact for new users
    if user.id is None:
        # Create a new contact with username
        new_contact = Contact(
            Name=user.Username,
            Email=user.Email,
            Type='Member',
            Date_Created=date.today()
        )
        db.session.add(new_contact)
        db.session.flush() # Get ID
        user.Contact_ID = new_contact.id
        
        # Also create ContactClub record to link contact to current club
        from .club_context import get_current_club_id
        club_id = get_current_club_id()
        if not club_id:
            default_club = Club.query.first()
            club_id = default_club.id if default_club else None
        
        if club_id:
            from .models import ContactClub
            contact_club = ContactClub(
                contact_id=new_contact.id,
                club_id=club_id
            )
            db.session.add(contact_club)

    # Sync UserClub.contact_id if Contact_ID changed
    if user.id and user.Contact_ID and user.Contact_ID != old_contact_id:
        from .models import UserClub
        UserClub.query.filter_by(user_id=user.id).update({UserClub.contact_id: user.Contact_ID})
    
    # For new users, create UserClub record with pending role
    if hasattr(user, '_pending_role_id') and user._pending_role_id:
        if not user.id:
            db.session.flush()  # Ensure user has an ID
        
        # Get current or default club
        club_id = get_current_club_id()
        if not club_id:
            default_club = Club.query.first()
            club_id = default_club.id if default_club else None
        
        if club_id:
            new_uc = UserClub(
                user_id=user.id,
                club_id=club_id,
                club_role_id=user._pending_role_id,
                contact_id=user.Contact_ID
            )
            db.session.add(new_uc)
        
        delattr(user, '_pending_role_id')


@users_bp.route('/users')
@login_required
def show_users():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))


@users_bp.route('/user/form', defaults={'user_id': None}, methods=['GET', 'POST'])
@users_bp.route('/user/form/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_form(user_id):
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    user = None
    if user_id:
        user = User.query.get_or_404(user_id)

    member_contacts = Contact.query.filter(
        Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    mentor_contacts = Contact.query.filter(or_(
        Contact.Type == 'Member', Contact.Type == 'Past Member')).order_by(Contact.Name.asc()).all()
    users = User.query.order_by(User.Username.asc()).all()

    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    if request.method == 'POST':
        role_ids = request.form.getlist('roles', type=int)
        
        # Security check: Only SysAdmins can assign SysAdmin role
        from .models import AuthRole
        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        if sysadmin_role and sysadmin_role.id in role_ids:
            # Check if current user is a SysAdmin
            if not is_authorized(Permissions.SYSADMIN):
                flash("Only SysAdmins can assign the SysAdmin role.", 'error')
                return redirect(url_for('settings_bp.settings', default_tab='user-settings'))
        
        _create_or_update_user(
            user=user,
            username=request.form.get('username'),
            email=request.form.get('email'),
            role_ids=role_ids,
            status=request.form.get('status'),
            contact_id=request.form.get('contact_id', 0, type=int),
            create_new_contact=request.form.get('create_new_contact') == 'on',
            password=request.form.get('password')
        )
        db.session.commit()
        
        db.session.commit()

        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))


    from .models import AuthRole, UserClub
    all_auth_roles = AuthRole.query.order_by(AuthRole.id).all()
    
    # Security: Check if current user is actually a SysAdmin
    # We need to check the database directly to ensure accuracy
    sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
    current_user_is_sysadmin = False
    if sysadmin_role and current_user.is_authenticated:
        # Check if user has SysAdmin role in any club
        current_user_is_sysadmin = UserClub.query.filter_by(
            user_id=current_user.id, 
            club_role_id=sysadmin_role.id
        ).first() is not None
    
    # Filter roles based on permissions
    filtered_roles = []
    for role in all_auth_roles:
        # Only SysAdmins can see/assign SysAdmin role
        if role.name == 'SysAdmin' and not current_user_is_sysadmin:
            continue
        # Guest role should not be assignable in user management
        if role.name == 'Guest':
            continue
        filtered_roles.append(role)
    
    user_role_ids = [r.id for r in user.roles] if user else []

    return render_template('user_form.html', user=user, contacts=member_contacts, users=users, mentor_contacts=mentor_contacts, pathways=pathways, all_auth_roles=filtered_roles, user_role_ids=user_role_ids)


@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
    
    # Delete linked contact if exists
    if user.Contact_ID:
        contact = db.session.get(Contact, user.Contact_ID)
        if contact:
            db.session.delete(contact)
    
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))


@users_bp.route('/user/bulk_import', methods=['POST'])
@login_required
def bulk_import_users():
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

    file = request.files['file']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

    if file and file.filename.endswith('.csv'):
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_reader = csv.reader(stream)
        # Skip header row
        next(csv_reader, None)

        success_count = 0
        failed_users = []

        for row in csv_reader:
            if not row or len(row) < 2:
                continue

            fullname, username, member_id, email, mentor_name = (
                row + [None]*5)[:5]

            if not fullname or not username:
                failed_users.append(
                    f"Skipping row: Fullname and Username are mandatory. Row: {row}")
                continue

            # Duplication check
            if User.query.filter_by(Username=username).first():
                failed_users.append(
                    f"Skipping user '{username}': User already exists.")
                continue

            contact = Contact.query.filter_by(Name=fullname).first()
            contact_id = contact.id if contact else None

            mentor = Contact.query.filter_by(Name=mentor_name).first()
            mentor_id = mentor.id if mentor else None

            _create_or_update_user(
                username=username,
                contact_id=contact_id,
                email=email,
                member_id=member_id,
                mentor_id=mentor_id,
                role='User',
                password='leadership'
            )
            success_count += 1

        db.session.commit()
        flash(f'{success_count} users imported successfully.', 'success')
        if failed_users:
            flash('Some users failed to import:', 'error')
            for failure in failed_users:
                flash(failure, 'error')

    else:
        flash('Invalid file type. Please upload a .csv file.', 'error')

    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))
