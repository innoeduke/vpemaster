import os
import csv
import io
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app, jsonify
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from vpemaster.models import Contact
from .main_routes import login_required

agenda_bp = Blueprint('agenda_bp', __name__)

def _generate_agenda_items(filename):
    """
    Generates the agenda items from a given file.
    """
    agenda_items = []

    # Use an absolute path to be safe
    abs_filename = os.path.join(current_app.root_path, 'agendas', os.path.basename(filename))

    try:
        with open(abs_filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: The agenda file could not be found: {os.path.basename(filename)}", 500, None
    except Exception as e:
        return f"An error occurred while reading the agenda file: {e}", 500, None

    if not lines:
        return "Error: The agenda file is empty.", 500, None

    first_line = lines[0].strip()
    time_match = re.search(r'\d{1,2}:\d{2}', first_line)

    if not time_match:
        return "Error: Could not find a valid start time in HH:MM format on the first line.", 500

    start_time_str = time_match.group(0)

    try:
        current_time = datetime.strptime(start_time_str, '%H:%M')
    except ValueError:
        return f"Error: Found '{start_time_str}', but it is not a valid time.", 500

    # Store start time to reconstruct file later
    agenda_start_time = start_time_str

    for i, line in enumerate(lines[1:], 2):
        line = line.strip()
        if not line:
            continue

        parts = line.split(',')
        if len(parts) == 1:
            section_title = parts[0].strip()
            agenda_items.append({'time': '', 'title': section_title, 'is_section': True})
            continue

        if len(parts) != 3:
            return f"Error on line {i}: Each session must have a title, owner, and duration, separated by commas.", 500

        title, owner, duration_str = [p.strip() for p in parts]

        try:
            duration = int(duration_str)
        except ValueError:
            return f"Error on line {i}: The duration '{duration_str}' is not a valid number.", 500

        agenda_items.append({'time': current_time.strftime('%H:%M'), 'title': title, 'owner': owner, 'raw_owner': owner, 'duration': duration, 'is_section': False})

        if agenda_items and "Networking" not in agenda_items[-1]['title']:
             current_time += timedelta(minutes=1)

        if agenda_items and agenda_items[-1]['title'].startswith('Evaluator'):
            current_time += timedelta(minutes=1)

        current_time += timedelta(minutes=duration)

        if owner:
            contact = Contact.query.filter_by(Name=owner).first()
            if contact:
                updated_owner = owner
                if contact.Club == 'Guest':
                    updated_owner = f"{owner} - Guest"
                elif contact.Club and contact.Club != 'SHLTMC':
                    updated_owner = f"{owner}@{contact.Club}"
                elif contact.Completed_Levels:
                    updated_owner = f"{owner} - {contact.Completed_Levels}"
                agenda_items[-1]['owner'] = updated_owner

    return agenda_items, None, agenda_start_time


@agenda_bp.route('/agenda', methods=['GET'])
@login_required
def agenda():
    UPLOAD_FOLDER = os.path.join(current_app.root_path, 'agendas')
    active_filename = session.get('active_agenda_filename', 'default.csv')
    active_agenda_path = os.path.join(UPLOAD_FOLDER, active_filename)

    agenda_items, error_code, _ = _generate_agenda_items(active_agenda_path)

    contacts_query = Contact.query.order_by(Contact.Name.asc()).all()
    # Convert contact objects to a list of dictionaries to be JSON-safe
    contacts_data = [{"Name": c.Name} for c in contacts_query]

    if error_code:
        flash(agenda_items, 'error')
        if 'active_agenda_filename' in session:
            session.pop('active_agenda_filename')
            return redirect(url_for('agenda_bp.agenda'))
        return render_template('agenda.html', agenda_items=[], contacts=contacts_data)

    return render_template('agenda.html', agenda_items=agenda_items, contacts=contacts_data)

@agenda_bp.route('/agenda/save', methods=['POST'])
@login_required
def save_agenda():
    if session.get('user_role') not in ['Admin', 'Officer']:
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    UPLOAD_FOLDER = os.path.join(current_app.root_path, 'agendas')
    active_filename = session.get('active_agenda_filename', 'default.csv')
    file_path = os.path.join(UPLOAD_FOLDER, secure_filename(active_filename))

    # To save the file, we need the original start time
    _, _, start_time = _generate_agenda_items(file_path)

    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            f.write(f"{start_time}\n") # Removed for simplicity in saving
            for item in data:
                if item['type'] == 'section':
                    f.write(f"{item['title']}\n")
                else:
                    f.write(f"{item['title']},{item['owner']},{item['duration']}\n")
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/import', methods=['POST'])
@login_required
def import_agenda_from_csv():
    UPLOAD_FOLDER = os.path.join(current_app.root_path, 'agendas')

    if 'file' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('agenda_bp.agenda'))

    file = request.files['file']

    if file.filename == '':
        flash('No file was selected.', 'error')
        return redirect(url_for('agenda_bp.agenda'))

    if file and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(save_path)
        session['active_agenda_filename'] = filename
        flash(f"'{filename}' has been imported successfully!", 'success')
    else:
        flash('Invalid file type. Please upload a .csv file.', 'error')

    return redirect(url_for('agenda_bp.agenda'))


@agenda_bp.route('/export_agenda')
@login_required
def export_agenda_to_csv():
    UPLOAD_FOLDER = os.path.join(current_app.root_path, 'agendas')
    active_filename = session.get('active_agenda_filename', 'default.csv')
    active_agenda_path = os.path.join(UPLOAD_FOLDER, active_filename)

    agenda_items, error_code, _ = _generate_agenda_items(active_agenda_path)

    if error_code:
        flash(agenda_items, "error")
        return redirect(url_for('agenda_bp.agenda'))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Time', 'Title', 'Owner', 'Duration (min)'])

    for item in agenda_items:
        if item.get('is_section'):
            writer.writerow(['', item['title'], '', ''])
        else:
            writer.writerow([item.get('time', ''), item.get('title', ''), item.get('owner', ''), item.get('duration', '')])

    output.seek(0)
    export_filename = f"exported_{active_filename}"

    return send_file(io.BytesIO(output.getvalue().encode('utf-8')),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name=export_filename)