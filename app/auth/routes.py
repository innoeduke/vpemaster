from flask import render_template, request, redirect, url_for, session, flash, current_app, jsonify
from .permissions import Permissions
import os
from sqlalchemy import or_
from flask_login import login_user, logout_user, login_required, current_user

from . import auth_bp  # Import the blueprint
from .. import db       # Import db from the parent package
from ..models import User, Club
from ..club_context import set_current_club_id
from .email import send_reset_email

# API endpoint to lookup user clubs
@auth_bp.route('/lookup_user_clubs', methods=['POST'])
def lookup_user_clubs():
    """
    Lookup user's associated clubs based on username, email, or phone.
    Returns JSON with clubs array.
    """
    login_identifier = request.json.get('username', '').strip()
    
    if not login_identifier:
        return jsonify({'clubs': []})
    
    # Find user by username, email, or phone
    user = User.query.filter(
        or_(
            User.username == login_identifier,
            User.email == login_identifier,
            User.phone == login_identifier
        )
    ).first()
    
    if not user:
        return jsonify({'clubs': []})
    
    # Get user's associated clubs
    from ..models.user_club import UserClub
    from ..models import Club
    
    # If user is sysadmin, they can see all clubs
    if user.is_sysadmin:
        all_clubs = Club.query.order_by(Club.club_name).all()
        # Find user's home club to pre-select it if possible
        home_uc = UserClub.query.filter_by(user_id=user.id, is_home=True).first()
        home_club_id = home_uc.club_id if home_uc else None
        
        clubs_data = []
        for club in all_clubs:
            clubs_data.append({
                'id': club.id,
                'name': club.club_name,
                'is_home': club.id == home_club_id
            })
    else:
        # Regular user: only show their joined clubs
        user_clubs = UserClub.query.filter_by(user_id=user.id).all()
        clubs_data = []
        for uc in user_clubs:
            if uc.club:
                clubs_data.append({
                    'id': uc.club.id,
                    'name': uc.club.club_name,
                    'is_home': uc.is_home
                })
    
    return jsonify({'clubs': clubs_data})

# Login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.index'))

    if request.method == 'POST':
        login_identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Input validation
        if not login_identifier or not password:
            flash('Username, email, or phone and password are required.', 'error')
            return redirect(url_for('auth_bp.login'))
        
        if len(login_identifier) > 255 or len(password) > 128:
            flash('Input too long.', 'error')
            return redirect(url_for('auth_bp.login'))

        # DB Query
        user = User.query.filter(
            or_(
                User.username == login_identifier, 
                User.email == login_identifier,
                User.phone == login_identifier
            )
        ).first()

        # Constant time delay mitigation
        import time
        time.sleep(0.1)

        if user and user.check_password(password):
            if user.status != 'active':
                flash('Account is inactive.', 'error')
                return redirect(url_for('auth_bp.login'))

            login_user(user, remember=True)
            
            # Check for default password
            if password in ['leadership', 'toastmasters']:
                session['force_password_reset'] = True
                flash('Please change your default password immediately.', 'error')
                return redirect(url_for('auth_bp.profile', tab='password'))
            
            # Set current club ID from form
            club_id = request.form.get('club_names')
            if club_id:
                set_current_club_id(int(club_id))
            else:
                set_current_club_id(1)

            # Helper to redirect to 'next' page if present
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main_bp.index')
            return redirect(next_page)
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth_bp.login'))
            
    clubs = Club.query.filter(Club.club_no != '000001').all()
    return render_template('login.html', clubs=clubs)

# Logout route
@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('force_password_reset', None)
    session.pop('current_club_id', None)
    logout_user()
    return redirect(url_for('auth_bp.login'))

@auth_bp.before_app_request
def check_password_reset():
    if current_user.is_authenticated and session.get('force_password_reset'):
        # Allow static files and the profile page (where they can change password) and logout
        if request.endpoint not in ['auth_bp.profile', 'auth_bp.logout'] and \
           not request.endpoint.startswith('static') and \
           not request.endpoint.endswith('.static'):
            flash('You must change your password before continuing.', 'error')
            return redirect(url_for('auth_bp.profile', tab='password'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@auth_bp.route('/profile/<int:contact_id>', methods=['GET', 'POST'])
@login_required 
def profile(contact_id=None):
    """
    Displays a user's profile page and handles password reset.
    """
    # Guest Check: Block all guests from accessing profiles
    if current_user.primary_role_name == 'Guest':
        flash('Guests do not have access to user profiles.', 'error')
        return redirect(url_for('main_bp.index'))

    is_own_profile = True
    if contact_id and contact_id != current_user.contact_id:
        from ..models import Contact
        contact = Contact.query.get_or_404(contact_id)
        # Handle cases where contact might not have a user account
        if contact.user:
            user = contact.user
        else:
            class MockUser:
                def __init__(self, contact):
                    self.contact = contact
                    self.username = "No Account"
                    self.email = contact.Email
                    self.Role = contact.Type
                    self.home_club = None
                    self.member_no = contact.Member_ID
                    self.primary_role_name = contact.Type or "User"
                @property
                def primary_role(self):
                    return None
            user = MockUser(contact)
            
        is_own_profile = False

        # Permission Check for Viewing Other Profiles
        # Users (Members) can view other profiles, but guests cannot (handled above)
        can_view = True # Since Guest is already blocked, anyone else can view
             
        if not can_view:
            flash('Unauthorized access.', 'error')
            return redirect(url_for('auth_bp.profile'))
    else:
        user = current_user

    # Permission Check for Update Profile
    # Only the user himself/herself and clubadmin (for that club) or sysadmin can edit
    can_edit_profile = is_own_profile
    if not can_edit_profile:
        if current_user.is_sysadmin:
            can_edit_profile = True
        elif user.home_club and current_user.is_club_admin(user.home_club.id):
            can_edit_profile = True
    
    # Permission Check for Reset Password
    can_reset_password = can_edit_profile

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            if not can_edit_profile:
                 flash('You do not have permission to modify this profile.', 'error')
                 return redirect(url_for('auth_bp.profile', contact_id=contact_id))

            user.first_name = request.form.get('first_name')
            user.last_name = request.form.get('last_name')
            user.email = request.form.get('email')
            if user.contact:
                user.contact.Phone_Number = request.form.get('phone_number')
                user.contact.Bio = request.form.get('bio')
                
                # Handle Photo Upload
                file = request.files.get('profile_photo')
                if file and file.filename != '':
                    if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                        flash('Invalid image format. Supported formats: PNG, JPG, JPEG, GIF, WEBP', 'error')
                    else:
                        from ..utils import process_avatar
                        avatar_url = process_avatar(file, user.contact.id)
                        if avatar_url:
                            user.contact.Avatar_URL = avatar_url
                        else:
                            flash('Error processing image.', 'error')

            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('auth_bp.profile'))

        elif action == 'reset_password':
            if not can_reset_password:
                flash('You do not have permission to reset this user\'s password.', 'error')
                return redirect(url_for('auth_bp.profile', contact_id=contact_id))
            
            # Check for admin-initiated quick reset to default
            is_admin_reset = request.form.get('admin_reset') == 'true'
            if is_admin_reset and not is_own_profile:
                user.set_password('toastmasters')
                db.session.commit()
                flash(f'Password for {user.username} has been reset to "toastmasters".', 'success')
                return redirect(url_for('auth_bp.profile', contact_id=contact_id))
                
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if new_password:
                # Password strength validation
                if len(new_password) < 8:
                    flash('Password must be at least 8 characters long.', 'error')
                elif len(new_password) > 128:
                    flash('Password too long.', 'error')
                elif not any(c.isupper() for c in new_password):
                    flash('Password must contain at least one uppercase letter.', 'error')
                elif not any(c.islower() for c in new_password):
                    flash('Password must contain at least one lowercase letter.', 'error')
                elif not any(c.isdigit() for c in new_password):
                    flash('Password must contain at least one number.', 'error')
                elif new_password == confirm_password:
                    user.set_password(new_password) # Use the method
                    db.session.commit()
                    
                    # Clear session flag
                    session.pop('force_password_reset', None)
                    
                    flash('Your password has been updated successfully! Please log in with your new password.', 'success')
                    logout_user() # Logout ensuring clean state
                    return redirect(url_for('auth_bp.login'))
    return render_template('profile.html', user=user, is_own_profile=is_own_profile, can_reset_password=can_reset_password, can_edit_profile=can_edit_profile)


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            try:
                send_reset_email(user)
                flash('An email has been sent with instructions to reset your password.', 'info')
            except Exception as e:
                flash(f'Error sending email: {str(e)}', 'error')
            return redirect(url_for('auth_bp.login'))
        else:
            # For security, we might want to say "If that email exists...", 
            # but for this internal app, let's guide the user.
            flash('There is no account with that email. You must register first.', 'warning')
            
    return render_template('auth/reset_request.html')


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.index'))
    
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('auth_bp.reset_password_request'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or len(password) < 8:
             flash('Password must be at least 8 characters long.', 'error')
        elif password != confirm_password:
             flash('Passwords do not match.', 'error')
        else:
             # Basic strength check matching profile logic
             if not any(c.isupper() for c in password) or \
                not any(c.islower() for c in password) or \
                not any(c.isdigit() for c in password):
                  flash('Password must contain uppercase, lowercase and number.', 'error')
             else:
                  user.set_password(password)
                  db.session.commit()
                  flash('Your password has been updated! You are now able to log in', 'success')
                  return redirect(url_for('auth_bp.login'))
                  
    return render_template('auth/reset_token.html')