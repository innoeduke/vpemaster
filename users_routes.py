# vpemaster/users_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db
from vpemaster.models import User, Contact
from werkzeug.security import generate_password_hash
from .main_routes import login_required
from datetime import date

users_bp = Blueprint('users_bp', __name__)

def _create_or_update_user(user=None, **kwargs):
    """Helper function to create or update a user."""

    if user is None:
        # Creating a new user
        user = User(Date_Created=date.today())
        password = kwargs.get('password') or 'leadership'
        user.Pass_Hash = generate_password_hash(password)
        db.session.add(user)
    else:
        # Updating an existing user
        password = kwargs.get('password')
        if password:
            user.Pass_Hash = generate_password_hash(password)

    user.Username = kwargs.get('username')
    user.Email = kwargs.get('email')
    user.Member_ID = kwargs.get('member_id')
    user.Role = kwargs.get('role')

    contact_id = kwargs.get('contact_id', 0)
    user.Contact_ID = contact_id if contact_id != 0 else None

    mentor_id = kwargs.get('mentor_id', 0)
    user.Mentor_ID = mentor_id if mentor_id != 0 else None


@users_bp.route('/users')
@login_required
def show_users():
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

@users_bp.route('/user/form', defaults={'user_id': None}, methods=['GET', 'POST'])
@users_bp.route('/user/form/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_form(user_id):
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    user = None
    if user_id:
        user = User.query.get_or_404(user_id)

    contacts = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()
    users = User.query.order_by(User.Username.asc()).all()

    if request.method == 'POST':
        _create_or_update_user(
            user=user,
            username=request.form.get('username'),
            email=request.form.get('email'),
            member_id=request.form.get('member_id'),
            role=request.form.get('role'),
            contact_id=request.form.get('contact_id', 0, type=int),
            mentor_id=request.form.get('mentor_id', 0, type=int),
            password=request.form.get('password')
        )
        db.session.commit()
        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

    return render_template('user_form.html', user=user, contacts=contacts, users=users)

@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))