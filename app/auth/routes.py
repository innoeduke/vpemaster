from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_
from werkzeug.security import check_password_hash, generate_password_hash

from . import auth_bp  # Import the blueprint
from .. import db       # Import db from the parent package
from ..models import User
from .utils import login_required  # Import the decorator from app/auth.py

# Login route
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_identifier = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 输入验证
        if not login_identifier or not password:
            flash('Username/email and password are required.', 'error')
            return redirect(url_for('auth_bp.login'))
        
        if len(login_identifier) > 255 or len(password) > 128:
            flash('Input too long.', 'error')
            return redirect(url_for('auth_bp.login'))

        # 使用参数化查询防止SQL注入
        user = User.query.filter(
            or_(
                User.Username == login_identifier, 
                User.Email == login_identifier
            )
        ).first()

        # 添加固定延迟防止时序攻击
        import time
        time.sleep(0.1)  # 100ms延迟

        if user and check_password_hash(user.Pass_Hash, password):
            if user.Status != 'active':
                flash('Invalid username or password.', 'error')  # 统一错误消息
                return redirect(url_for('auth_bp.login'))

            session.clear() 
            session.permanent = False  # 设置为非永久会话
            session['logged_in'] = True
            session['user_role'] = user.Role
            session['user_id'] = user.id
            if user.contact:
                session['display_name'] = user.contact.Name
            # 登录后重新生成会话ID防止会话固定攻击
            return redirect(url_for('main_bp.index'))
        else:
            flash('Invalid username or password.', 'error')  # 统一错误消息
            return redirect(url_for('auth_bp.login'))
            
    # Note: Your login.html is in the root /templates, not /templates/auth
    # The blueprint will find it automatically.
    return render_template('login.html')

# Logout route
@auth_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_role', None)
    session.pop('user_id', None)
    session.pop('display_name', None)
    return redirect(url_for('auth_bp.login')) # <-- Use auth_bp

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required  # <-- This decorator now comes from app/auth.py
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
            return redirect(url_for('auth_bp.profile')) # <-- Use auth_bp

        elif action == 'reset_password':
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            if new_password:
                # 密码强度验证
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
                    user.Pass_Hash = generate_password_hash(new_password, method='pbkdf2:sha256')
                    db.session.commit()
                    flash('Your password has been updated successfully!', 'success')
                    return redirect(url_for('auth_bp.profile'))
                else:
                    flash('The new passwords do not match.', 'error')

    return render_template('profile.html', user=user)