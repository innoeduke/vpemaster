from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db, bcrypt
from vpemaster.models import User
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

    if request.method == 'POST':
        if user:
            user.Username = request.form['username']
            user.Full_Name = request.form.get('full_name')
            user.Display_Name = request.form.get('display_name')
            user.Role = request.form['role']
            password = request.form.get('password')
            if password:
                user.Pass_Hash = generate_password_hash(password)

            db.session.commit()
        else:
            username = request.form['username']
            full_name = request.form.get('full_name')
            display_name = request.form.get('display_name')
            password = request.form['password']
            role = request.form['role']

            pass_hash = generate_password_hash(password)

            new_user = User(
                Username=username,
                Full_Name=full_name,
                Display_Name=display_name,
                Date_Created=date.today(),
                Pass_Hash=pass_hash,
                Role=role
            )

            db.session.add(new_user)
            db.session.commit()

        return redirect(url_for('users_bp.show_users'))

    return render_template('user_form.html', user=user)

@users_bp.route('/user/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('users_bp.show_users'))
