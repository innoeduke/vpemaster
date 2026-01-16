from flask import render_template, request, redirect, url_for, session, flash, current_app
from .permissions import Permissions
import os
from sqlalchemy import or_
from flask_login import login_user, logout_user, login_required, current_user

from . import auth_bp  # Import the blueprint
from .. import db       # Import db from the parent package
from ..models import User, Club
from ..club_context import set_current_club_id
from .email import send_reset_email

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
            flash('Username/email and password are required.', 'error')
            return redirect(url_for('auth_bp.login'))
        
        if len(login_identifier) > 255 or len(password) > 128:
            flash('Input too long.', 'error')
            return redirect(url_for('auth_bp.login'))

        # DB Query
        user = User.query.filter(
            or_(
                User.Username == login_identifier, 
                User.Email == login_identifier
            )
        ).first()

        # Constant time delay mitigation
        import time
        time.sleep(0.1)

        if user and user.check_password(password):
            if user.Status != 'active':
                flash('Account is inactive.', 'error')
                return redirect(url_for('auth_bp.login'))

            login_user(user, remember=True)
            
            # Check for default password
            if password == 'leadership':
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
            
    clubs = Club.query.all()
    return render_template('login.html', clubs=clubs)

# Logout route
@auth_bp.route('/logout')
@login_required
def logout():
    session.pop('force_password_reset', None)
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
    is_own_profile = True
    if contact_id and contact_id != current_user.Contact_ID:
        if not current_user.has_role(Permissions.STAFF):
            flash('Unauthorized access.', 'error')
            return redirect(url_for('auth_bp.profile'))
        
        from ..models import Contact
        contact = Contact.query.get_or_404(contact_id)
        # Handle cases where contact might not have a user account
        if contact.user:
            user = contact.user
        else:
            # Create a mock user object to satisfy the template's needs if possible, 
            # or just pass the contact info. For now, let's assume they have accounts 
            # as these are journals. If not, we still show the contact info.
            class MockUser:
                def __init__(self, contact):
                    self.contact = contact
                    self.Username = "No Account"
                    self.Email = contact.Email
                    self.Role = contact.Type
            user = MockUser(contact)
        is_own_profile = False
    else:
        user = current_user

    if request.method == 'POST':
        if not is_own_profile:
            flash('You cannot modify someone else\'s profile.', 'error')
            return redirect(url_for('auth_bp.profile', contact_id=contact_id))

        action = request.form.get('action')

        if action == 'update_profile':
            user.Email = request.form.get('email')
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
    return render_template('profile.html', user=user, is_own_profile=is_own_profile)


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('main_bp.index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(Email=email).first()
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