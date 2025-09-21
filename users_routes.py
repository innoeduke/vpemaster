# vpemaster/users_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db
from vpemaster.models import User, Contact
from werkzeug.security import generate_password_hash
from .main_routes import login_required
from datetime import date

users_bp = Blueprint('users_bp', __name__)

@users_bp.route('/users')
@login_required
def show_users():
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    all_users = User.query.order_by(User.Username.asc()).all()
    return render_template('users.html', users=all_users)

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

    if request.method == 'POST':
        contact_id = request.form.get('contact_id', 0, type=int)

        if user:
            user.Username = request.form['username']
            user.Role = request.form['role']
            user.Contact_ID = contact_id if contact_id != 0 else None
            password = request.form.get('password')
            if password:
                user.Pass_Hash = generate_password_hash(password)
        else:
            pass_hash = generate_password_hash(request.form['password'])
            new_user = User(
                Username=request.form['username'],
                Pass_Hash=pass_hash,
                Role=request.form['role'],
                Contact_ID=contact_id if contact_id != 0 else None,
                Date_Created=date.today()
            )
            db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('users_bp.show_users'))

    return render_template('user_form.html', user=user, contacts=contacts)

@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('users_bp.show_users'))