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
    user.Email = kwargs.get('email')
    
    # Handle multiple roles
    role_ids = kwargs.get('role_ids', [])
    role_name = kwargs.get('role') # Legacy single-role support
    from .models import UserRoleAssociation, AuthRole, PermissionAudit
    from flask_login import current_user
    
    # If role_name is provided but role_ids is not, try to find the role
    if not role_ids and role_name:
        role_obj = AuthRole.query.filter_by(name=role_name).first()
        if role_obj:
            role_ids = [role_obj.id]

    if user.id:
        current_roles = UserRoleAssociation.query.filter_by(user_id=user.id).all()
        current_role_ids = {r.role_id for r in current_roles}
        new_role_ids = set(role_ids)

        if current_role_ids != new_role_ids:
            # To add
            for rid in new_role_ids - current_role_ids:
                db.session.add(UserRoleAssociation(user_id=user.id, role_id=rid))

            # To remove
            for r in current_roles:
                if r.role_id not in new_role_ids:
                    db.session.delete(r)

            # Audit log
            if current_user.is_authenticated:
                audit = PermissionAudit(
                    admin_id=current_user.id,
                    action='UPDATE_USER_ROLES',
                    target_type='USER',
                    target_id=user.id,
                    target_name=user.Username,
                    changes=f"Updated roles: {list(new_role_ids)}"
                )
                db.session.add(audit)
    else:
        # For new users, we'll assign roles after commit to get user.id
        # We store them in the user object temporarily or handle after commit.
        # Let's handle it after commit in the callers for now, 
        # but _create_or_update_user should really handle the flush/commit if it's responsible for roles.
        # Alternatively, we can use user.roles relationship if it's set up correctly.
        if role_ids:
            # If we have AuthRole objects, we could append. If we have IDs, we need to fetch.
            for rid in role_ids:
                robj = db.session.get(AuthRole, rid)
                if robj:
                    user.roles.append(robj)

    # Profile fields (Member_ID, Current_Path, etc.) are now on Contact model.
    # We do not set them here.

    create_new_contact = kwargs.get('create_new_contact', False)
    if create_new_contact and user.id is None:
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
    else:
        contact_id = kwargs.get('contact_id', 0)
        user.Contact_ID = contact_id if contact_id != 0 else None


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

    from .models import AuthRole
    all_auth_roles = AuthRole.query.order_by(AuthRole.id).all()
    user_role_ids = [r.id for r in user.roles] if user else []

    return render_template('user_form.html', user=user, contacts=member_contacts, users=users, mentor_contacts=mentor_contacts, pathways=pathways, all_auth_roles=all_auth_roles, user_role_ids=user_role_ids)


@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
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


@users_bp.route('/user/quick_add/<int:contact_id>', methods=['POST'])
@login_required
def quick_add_user(contact_id):
    if not is_authorized(Permissions.CONTACT_BOOK_EDIT):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('contacts_bp.show_contacts'))

    contact = Contact.query.get_or_404(contact_id)

    if contact.user:
        flash(f'Contact {contact.Name} already has a user account.', 'error')
        return redirect(url_for('contacts_bp.show_contacts'))

    # Derive username logic:
    # 1. Split name into First and Last (last token)
    # 2. Max length 8.
    # 3. Strategy: 
    #    - If First+Last <= 8 chars: Use combined.
    #    - Else: Prioritize Last Name (up to 7 chars). Fill remainder with First Name.
    #    - Ex: "Christopher Lee" -> "chrislee" (Last=3, First=5)
    #    - Ex: "John Longlastname" -> "jlongname" (Last=7, First=1)
    
    parts = contact.Name.strip().split()
    if not parts:
        # Fallback for empty name? Should not happen for valid contact.
        base_username = f"user{contact.id}"
    elif len(parts) == 1:
        base_username = parts[0].lower()[:8]
    else:
        first_name = parts[0].lower()
        last_name = parts[-1].lower()
        
        # Remove non-alphanumeric characters if needed? 
        # Requirement simple: just letters. Let's assume input is clean or just slice.
        # Ideally, we should filter for alphanumeric to avoid "O'Reilly" issues in username.
        first_name = "".join(filter(str.isalnum, first_name))
        last_name = "".join(filter(str.isalnum, last_name))
        
        combined = first_name + last_name
        if len(combined) <= 8:
            base_username = combined
        else:
            # We need to cut.
            # Max possible chars from last name is 7 (leaving 1 for first name at minimum implicit in "first letter...")
            # Actually user said: "use more letters from the first name to backfill [if last is short]"
            # This implies:
            # Target total = 8.
            # Len Last used = min(len(last_name), 7)
            # Len First used = 8 - Len Last used
            
            len_last_used = min(len(last_name), 7)
            len_first_used = 8 - len_last_used
            
            # Ensure we have enough first name chars (usually yes if len > 8 total)
            # But edge case: "A Verylongname" (First=1, Last=12).
            # Last used = 7 ("Verylon"). First used = 1 ("A"). Total 8. Matches.
            
            base_username = first_name[:len_first_used] + last_name[:len_last_used]
            
    # Simple uniqueness check
    username = base_username
    counter = 1
    while User.query.filter_by(Username=username).first():
        # If duplicated, append number? User said "avoid duplication".
        # Appending number increases length > 8 potentially.
        # But uniqueness is hard constraint.
        username = f"{base_username}{counter}"
        counter += 1

    try:
        _create_or_update_user(
            username=username,
            contact_id=contact.id,
            email=contact.Email,
            role='User',
            status='active',
            password='leadership'
        )
        
        # Update contact type to Member
        contact.Type = 'Member'
        
        db.session.commit()
        flash(f'User created for {contact.Name} with username: {username}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'error')

    return redirect(url_for('contacts_bp.show_contacts'))
