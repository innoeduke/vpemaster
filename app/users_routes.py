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
from .club_context import get_current_club_id

users_bp = Blueprint('users_bp', __name__)


def _save_user_data(user=None, **kwargs):
    """
    Orchestrates user creation/updating.
    Separates business logic (roles, audit) from data logic (model).
    """
    from .models import AuthRole, PermissionAudit, Club, Contact
    from .club_context import get_current_club_id
    
    # 1. Create or Update User instance
    is_new = user is None
    is_sysadmin = is_authorized(Permissions.SYSADMIN)
    if is_new:
        user = User(
            username=kwargs.get('username'),
            created_at=date.today(),
            status='active'
        )
        password = kwargs.get('password') or 'leadership'
        user.set_password(password)
        db.session.add(user)
    else:
        # Existing User - Only allow SysAdmin to update these fields
        if is_sysadmin:
            if kwargs.get('username'):
                user.username = kwargs.get('username')
            password = kwargs.get('password')
            if password:
                user.set_password(password)
            if kwargs.get('status'):
                user.status = kwargs.get('status')
    
    # Update names - Only if NEW or current_user is SysAdmin
    if is_new or is_sysadmin:
        if kwargs.get('first_name'):
            user.first_name = kwargs.get('first_name')
        if kwargs.get('last_name'):
            user.last_name = kwargs.get('last_name')

        # Update other fields
        user.phone = kwargs.get('phone')
        user.email = kwargs.get('email') if kwargs.get('email') is not None else None

    # Ensure ID exists for relationships
    db.session.flush()

    # Link existing contact if provided
    contact_id = kwargs.get('contact_id')
    create_new_contact = kwargs.get('create_new_contact')
    club_id = kwargs.get('club_id') or get_current_club_id()
    
    # 1. User selected an existing contact to link
    if contact_id and contact_id != 0 and not create_new_contact:
        # Verify contact exists AND strictly belongs to the target club to prevent cross-club leakage
        from .models import ContactClub
        is_in_club = ContactClub.query.filter_by(contact_id=contact_id, club_id=club_id).first()
        if is_in_club:
            contact = db.session.get(Contact, contact_id)
            if contact and club_id:
                from .models import UserClub
                uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
                if uc:
                    uc.contact_id = contact_id
                else:
                    db.session.add(UserClub(user_id=user.id, club_id=club_id, contact_id=contact_id))

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
    # Logic: Calculate highest role from bitmask (role_level) and assign to CURRENT club
    role_level = kwargs.get('role_level')
    if role_level is None and is_new:
        role_level = 1 # Default User
        
    highest_role_id = None
    if role_level is not None and role_level > 0:
        user.set_club_role(club_id, role_level)
        
        # 4. Audit Log
        if current_user and current_user.is_authenticated:
             audit = PermissionAudit(
                 admin_id=current_user.id,
                 action='UPDATE_USER_ROLES',
                 target_type='USER',
                 target_id=user.id,
                 target_name=user.username,
                 changes=f"Updated role level to: {role_level}"
             )
             db.session.add(audit)
    
    return user



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
        role_ids = request.form.getlist('roles', type=int)
        
        # Security check: Only SysAdmins can assign SysAdmin role
        from .models import AuthRole
        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        if sysadmin_role and sysadmin_role.id in role_ids:
            # Check if current user is a SysAdmin
            if not is_authorized(Permissions.SYSADMIN):
                flash("Only SysAdmins can assign the SysAdmin role.", 'error')
                return redirect(url_for('settings_bp.settings', default_tab='user-settings'))
        
        # Calculate role_level from role_ids
        role_level = 0
        if role_ids:
             roles = AuthRole.query.filter(AuthRole.id.in_(role_ids)).all()
             for r in roles:
                 role_level += r.level if r.level else 0
        
        _save_user_data(
            user=user,
            username=request.form.get('username'),
            full_name=request.form.get('full_name'),
            first_name=request.form.get('first_name'),
            last_name=request.form.get('last_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            role_level=role_level,
            status=request.form.get('status'),
            contact_id=request.form.get('contact_id', 0, type=int),
            create_new_contact=request.form.get('create_new_contact') == 'on',
            password=request.form.get('password'),
            club_id=club_id
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
        user_clubs = UserClub.query.filter_by(user_id=current_user.id).all()
        current_user_is_sysadmin = any((uc.club_role_level & sysadmin_role.level) == sysadmin_role.level for uc in user_clubs)
    
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
    
    user_role_ids = []
    user_contact = None
    is_edit_self = False
    
    if user:
        is_edit_self = (user.id == current_user.id)
        # Fix: Only load roles/contact for the specific club context to prevent leakage
        from .models import UserClub
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
        if uc:
            if uc.roles:
                user_role_ids.extend([r.id for r in uc.roles])
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

    return render_template('user_form.html', user=user, user_contact=user_contact, source_contact=source_contact, 
                           contacts=member_contacts, mentor_contacts=mentor_contacts, pathways=pathways, 
                           all_auth_roles=filtered_roles, user_role_ids=user_role_ids, 
                           club_id=club_id, club_name=club_name, is_edit_self=is_edit_self,
                           current_user_is_sysadmin=current_user_is_sysadmin)


@users_bp.route('/user/check_duplicates', methods=['POST'])
@login_required
def check_duplicates():
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
    if not is_authorized(Permissions.SETTINGS_VIEW_ALL):
        return redirect(url_for('agenda_bp.agenda'))

    user = db.get_or_404(User, user_id)
    current_club_id = get_current_club_id()
    
    from .models import UserClub, ContactClub
    
    # 1. Find and delete UserClub entry for this club
    uc = UserClub.query.filter_by(user_id=user.id, club_id=current_club_id).first()
    contact = None
    
    if uc:
        contact = uc.contact
        db.session.delete(uc)
    else:
        # Fallback: Try to find contact via User method if UserClub is missing
        contact = user.get_contact(current_club_id)
        
    # Flush to ensure UserClub deletion is registered for subsequent counts
    db.session.flush()
    
    # 2. Handle Contact and ContactClub
    if contact:
        # Delete ContactClub entry for this club
        cc = ContactClub.query.filter_by(contact_id=contact.id, club_id=current_club_id).first()
        if cc:
            db.session.delete(cc)
            db.session.flush()
            
        # Check if Contact is orphaned (not used in any other club)
        # We check both ContactClub (membership) and UserClub (user link)
        other_cc_count = ContactClub.query.filter_by(contact_id=contact.id).count()
        other_uc_count = UserClub.query.filter_by(contact_id=contact.id).count()
        
        if other_cc_count == 0 and other_uc_count == 0:
            db.session.delete(contact)
            
    # 3. Check if User is orphaned
    remaining_clubs = UserClub.query.filter_by(user_id=user.id).count()
    
    # Exception: SysAdmin account doesn't need to be associated with a club
    # We identify SysAdmin by username 'sysadmin' (common convention)
    is_sysadmin_account = user.username.lower() in ('sysadmin', 'admin')
    
    if remaining_clubs == 0 and not is_sysadmin_account:
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
            if User.query.filter_by(username=username).first():
                failed_users.append(
                    f"Skipping user '{username}': User already exists.")
                continue

            contact = Contact.query.filter_by(Name=fullname).first()
            contact_id = contact.id if contact else None

            mentor = Contact.query.filter_by(Name=mentor_name).first()
            mentor_id = mentor.id if mentor else None

            from .models import AuthRole
            user_role = AuthRole.query.filter_by(name='User').first()
            role_level = user_role.level if user_role else 1

            _save_user_data(
                username=username,
                email=email,
                role_level=role_level,
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
