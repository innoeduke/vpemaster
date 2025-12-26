from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_
from flask_login import login_user, logout_user, login_required, current_user

from . import auth_bp  # Import the blueprint
from .. import db       # Import db from the parent package
from ..models import User

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
            
            # Helper to redirect to 'next' page if present
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main_bp.index')
            return redirect(next_page)
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('auth_bp.login'))
            
    return render_template('login.html')

# Logout route
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required 
def profile():
    """
    Displays the logged-in user's profile page and handles password reset.
    """
    user = current_user

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            user.Email = request.form.get('email')
            if user.contact:
                user.contact.Phone_Number = request.form.get('phone_number')
                user.contact.Bio = request.form.get('bio')
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
                    flash('Your password has been updated successfully! Please log in with your new password.', 'success')
                    logout_user() # Logout ensuring clean state
                    return redirect(url_for('auth_bp.login'))
                else:
                    flash('The new passwords do not match.', 'error')

    return render_template('profile.html', user=user)