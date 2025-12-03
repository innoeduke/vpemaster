from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from . import db
from .models import User, Contact, Pathway
from .auth.utils import is_authorized, login_required
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
        user.Pass_Hash = generate_password_hash(password)
        user.Status = 'active'
        db.session.add(user)
    else:
        # Updating an existing user
        password = kwargs.get('password')
        if password:
            user.Pass_Hash = generate_password_hash(password)
        user.Status = kwargs.get('status')

    user.Username = kwargs.get('username')
    user.Email = kwargs.get('email')
    user.Member_ID = kwargs.get('member_id')
    user.Role = kwargs.get('role')
    user.Current_Path = kwargs.get('current_path') or None
    user.Next_Project = kwargs.get('next_project') or None
    user.credentials = kwargs.get('credential') or None

    contact_id = kwargs.get('contact_id', 0)
    user.Contact_ID = contact_id if contact_id != 0 else None

    mentor_id = kwargs.get('mentor_id', 0)
    user.Mentor_ID = mentor_id if mentor_id != 0 else None


@users_bp.route('/users')
@login_required
def show_users():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))


@users_bp.route('/user/form', defaults={'user_id': None}, methods=['GET', 'POST'])
@users_bp.route('/user/form/<int:user_id>', methods=['GET', 'POST'])
@login_required
def user_form(user_id):
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    user = None
    if user_id:
        user = User.query.get_or_404(user_id)

    member_contacts = Contact.query.filter(
        Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    mentor_contacts = Contact.query.filter(or_(
        Contact.Type == 'Member', Contact.Type == 'Past Member')).order_by(Contact.Name.asc()).all()
    users = User.query.order_by(User.Username.asc()).all()

    pathways = [p.name for p in Pathway.query.order_by(Pathway.name).all()]

    if request.method == 'POST':
        _create_or_update_user(
            user=user,
            username=request.form.get('username'),
            email=request.form.get('email'),
            member_id=request.form.get('member_id'),
            role=request.form.get('role'),
            status=request.form.get('status'),
            contact_id=request.form.get('contact_id', 0, type=int),
            mentor_id=request.form.get('mentor_id', 0, type=int),
            current_path=request.form.get('current_path'),
            next_project=request.form.get('next_project'),
            credential=request.form.get('credential'),
            password=request.form.get('password')
        )
        db.session.commit()
        return redirect(url_for('settings_bp.settings', default_tab='user-settings'))

    return render_template('user_form.html', user=user, contacts=member_contacts, users=users, mentor_contacts=mentor_contacts, pathways=pathways)


@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('settings_bp.settings', default_tab='user-settings'))


@users_bp.route('/user/bulk_import', methods=['POST'])
@login_required
def bulk_import_users():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
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
                role='Member',
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
