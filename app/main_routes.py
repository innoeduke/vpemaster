from flask import Blueprint, redirect, url_for, request, jsonify
from .auth.utils import login_required, current_user
from app.system_messaging import send_system_message
from app.models.user import User

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('agenda_bp.agenda'))

@main_bp.route('/api/report-bug', methods=['POST'])
@login_required
def report_bug():
    try:
        data = request.get_json()
        subject = data.get('subject')
        description = data.get('description')
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
            
        # Find SysAdmin user
        # User requested specifically sending to user with username 'sysadmin'
        sysadmin = User.query.filter_by(username='sysadmin').first()
        
        if not sysadmin:
            return jsonify({'success': False, 'error': 'System administrator not found'}), 404
            
        full_subject = f"Bug Report: {subject}"
        body = f"User: {current_user.username} ({current_user.display_name})\n\n{description}"
        
        success, message = send_system_message(sysadmin.id, full_subject, body)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': message}), 500
            
    except Exception as e:
        print(f"Error reporting bug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500