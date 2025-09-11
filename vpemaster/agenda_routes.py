import os
import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from vpemaster.models import Contact

agenda_bp = Blueprint('agenda_bp', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'agendas')
DEFAULT_AGENDA_FILE = os.path.join(UPLOAD_FOLDER, 'default.csv')
CUSTOM_AGENDA_FILE = os.path.join(UPLOAD_FOLDER, 'custom_agenda.csv')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('main_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

def _generate_agenda_items(filename):
    """
    Generates the agenda items from a given file.
    """
    agenda_items = []

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "Error: Agenda template file not found.", 500
    except Exception as e:
        return f"Error reading agenda file: {e}", 500

    # The first line is the meeting start time
    start_time_str = lines[0].strip()
    try:
        current_time = datetime.strptime(start_time_str, '%H:%M')
    except ValueError:
        return "Error: Invalid time format in template file. Please use HH:MM.", 500

    # Process remaining lines
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split(',')
        if len(parts) == 1:
            # It's a section title
            section_title = parts[0].strip()
            agenda_items.append({'time': '', 'title': section_title, 'is_section': True})
            continue

        # It's a session
        if len(parts) != 3:
            return f"Error: Invalid session format in template file: {line}", 500

        title, owner, duration_str = [p.strip() for p in parts]

        try:
            duration = int(duration_str)
        except ValueError:
            return f"Error: Invalid duration for session: {line}", 500

        agenda_items.append({'time': current_time.strftime('%H:%M'), 'title': title, 'owner': owner, 'duration': duration, 'is_section': False})

        # Add 1-minute break after previous session
        if agenda_items and agenda_items[-1]['title'] != 'Networking':
             current_time += timedelta(minutes=1)

        # Add 1-minute break after evaluation sessions
        if agenda_items and agenda_items[-1]['title'].startswith('Evaluator'):
            current_time += timedelta(minutes=1)

        # Calculate the end time of the session
        current_time += timedelta(minutes=duration)

        if owner:
            contact = Contact.query.filter_by(Name=owner).first()
            if contact:
                updated_owner = owner
                if contact.Club == 'Guest':
                    updated_owner = f"{owner} - Guest"
                elif contact.Club != 'SHLTMC':
                    updated_owner = f"{owner}@{contact.Club}"
                elif contact.Completed_Levels:
                    updated_owner = f"{owner} - {contact.Completed_Levels}"
                agenda_items[-1]['owner'] = updated_owner

    return agenda_items, None

@agenda_bp.route('/agenda', methods=['GET'])
@login_required
def agenda():
    # Set the active file based on session or fallback to default
    active_agenda_file = session.get('active_agenda', DEFAULT_AGENDA_FILE)

    agenda_items, error = _generate_agenda_items(active_agenda_file)

    if error:
        flash(error, 'error')
        # Fallback to default if the custom file fails to load
        if active_agenda_file == CUSTOM_AGENDA_FILE:
            session.pop('active_agenda', None)
        return redirect(url_for('agenda_bp.agenda'))

    return render_template('agenda.html', agenda_items=agenda_items)

@agenda_bp.route('/agenda/import', methods=['POST'])
@login_required
def import_agenda_from_csv():
    if 'file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('agenda_bp.agenda'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('agenda_bp.agenda'))

    if file and file.filename.endswith('.csv'):
        file.save(CUSTOM_AGENDA_FILE)
        session['active_agenda'] = CUSTOM_AGENDA_FILE
        flash('Agenda imported successfully!', 'success')
    else:
        flash('Invalid file type. Please upload a CSV file.', 'error')

    return redirect(url_for('agenda_bp.agenda'))

@agenda_bp.route('/export_agenda')
@login_required
def export_agenda_to_csv():
    active_agenda_file = session.get('active_agenda', DEFAULT_AGENDA_FILE)
    agenda_items, error = _generate_agenda_items(active_agenda_file)

    if error:
        flash(error, "error")
        return redirect(url_for('agenda_bp.agenda'))

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Time', 'Title', 'Owner', 'Duration (min)'])

    for item in agenda_items:
        if item.get('is_section'):
            writer.writerow(['', item['title'], '', ''])
        else:
            writer.writerow([item['time'], item['title'], item.get('owner', ''), item.get('duration', '')])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='meeting_agenda.csv')
