from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from . import db
from .models import User
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import or_

main_bp = Blueprint('main_bp', __name__)

# Decorator to check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('main_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

# Login route
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_identifier = request.form['username'] # This can be username or email
        password = request.form['password']

        # Query for user by username or email
        user = User.query.filter(or_(User.Username == login_identifier, User.Email == login_identifier)).first()

        if user and check_password_hash(user.Pass_Hash, password):
            if user.Status != 'active':
                flash('Your account is inactive. Please contact an administrator.', 'error')
                return redirect(url_for('main_bp.login'))
            session.permanent = True
            session['logged_in'] = True
            session['user_role'] = user.Role
            session['user_id'] = user.id
            if user.contact:
                session['display_name'] = user.contact.Name
            return redirect(url_for('agenda_bp.agenda'))
        else:
            flash('Invalid username or password.', 'error')
            return redirect(url_for('main_bp.login'))
    return render_template('login.html')

# Logout route
@main_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_role', None)
    session.pop('user_id', None)
    session.pop('display_name', None)
    return redirect(url_for('main_bp.login'))

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Displays the logged-in user's profile page and handles password reset.
    """
    user = User.query.get_or_404(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            user.Email = request.form.get('email')
            if user.contact:
                user.contact.Phone_Number = request.form.get('phone_number')
                user.contact.Bio = request.form.get('bio')
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('main_bp.profile'))

        elif action == 'reset_password':
            # Check if the request contains password fields for reset
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if new_password:
                if len(new_password) < 8:
                    flash('Password must be at least 8 characters long.', 'error')
                elif new_password == confirm_password:
                    # Update password hash
                    user.Pass_Hash = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Your password has been updated successfully!', 'success')
                    # POST-redirect-GET pattern
                    return redirect(url_for('main_bp.profile'))
                else:
                    flash('The new passwords do not match.', 'error')

    return render_template('profile.html', user=user)


@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('agenda_bp.agenda'))