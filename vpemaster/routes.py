from vpemaster import app, db
from flask import render_template, request, redirect, url_for, flash, send_file
from vpemaster.models import SpeechLog, Contact
from datetime import date, datetime, timedelta
import io
import csv
import os

def _generate_agenda_items():
    """
    Generates the agenda items from the template file.
    This is a helper function to avoid code duplication.
    """

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TEMPLATE_FILE = os.path.join(BASE_DIR, '..', 'agendas', 'agenda_default.csv')

    agenda_items = []

    try:
        with open(TEMPLATE_FILE, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return "Error: Agenda template file not found.", 500

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

@app.route('/')
def index():
    return '<h1>Welcome to the VPE Master App!</h1>'

@app.route('/agenda', methods=['GET', 'POST'])
def agenda():
    agenda_items, error = _generate_agenda_items()
    if error:
        return error, 500
    return render_template('agenda.html', agenda_items=agenda_items)


@app.route('/export_agenda')
def export_agenda_to_csv():

    agenda_items, error = _generate_agenda_items()
    if error:
        flash(error, "error")
        return redirect(url_for('agenda'))

    # Create CSV file in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Time', 'Title', 'Owner', 'Duration (min)'])

    # Write data
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

@app.route('/speech_logs')
def show_speech_logs():
    all_logs = SpeechLog.query.order_by(SpeechLog.Meeting_Number.asc()).all()
    return render_template('speech_logs.html', logs=all_logs)

@app.route('/speech_log/<int:log_id>', methods=['GET'])
def speech_log_form(log_id=None):
    if log_id:
        log = SpeechLog.query.get_or_404(log_id)
        return render_template('speech_log_form.html', log=log)
    return render_template('speech_log_form.html', log=None)

@app.route('/speech_log/<int:log_id>', methods=['POST'])
def save_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    log.Meeting_Number = request.form['meeting_number']
    log.Meeting_Date = datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date()
    log.Session = request.form['session']
    log.Speech_Title = request.form['speech_title']
    log.Pathway = request.form['pathway']
    log.Level = request.form['level']
    log.Name = request.form['name']
    log.Evaluator = request.form['evaluator']
    log.Project_Title = request.form['project_title']
    log.Project_Type = request.form['project_type']
    log.Project_Status = request.form['project_status']

    db.session.commit()
    flash('Speech Log updated successfully!')
    return redirect(url_for('show_speech_logs'))

@app.route('/speech_log/add', methods=['GET', 'POST'])
def add_speech_log():
    if request.method == 'POST':
        new_log = SpeechLog(
            Meeting_Number=request.form['meeting_number'],
            Meeting_Date=datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date(),
            Session=request.form['session'],
            Speech_Title=request.form['speech_title'],
            Pathway=request.form['pathway'],
            Level=request.form['level'],
            Name=request.form['name'],
            Evaluator=request.form['evaluator'],
            Project_Title=request.form['project_title'],
            Project_Type=request.form['project_type'],
            Project_Status=request.form['project_status']
        )
        db.session.add(new_log)
        db.session.commit()
        flash('New Speech Log added successfully!')
        return redirect(url_for('show_speech_logs'))
    return render_template('speech_log_form.html')

@app.route('/speech_log/delete/<int:log_id>', methods=['POST'])
def delete_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    flash('Speech Log deleted successfully!')
    return redirect(url_for('show_speech_logs'))

@app.route('/speech_log/complete/<int:log_id>', methods=['POST'])
def complete_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    log.Project_Status = 'Completed'
    db.session.commit()
    flash('Project status updated to Completed!')
    return redirect(url_for('show_speech_logs'))

@app.route('/contacts')
def show_contacts():
    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    return render_template('contacts.html', contacts=contacts)

@app.route('/contact/', defaults={'contact_id': None}, methods=['GET', 'POST'])
@app.route('/contact/<int:contact_id>', methods=['GET', 'POST'])
def contact_form(contact_id):
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)
        if request.method == 'POST':
            contact.Name = request.form['name']
            contact.Club = request.form['club']
            contact.Current_Project = request.form['current_project']
            contact.Completed_Levels = request.form['completed_levels']
            db.session.commit()
            flash('Contact updated successfully!')
            return redirect(url_for('show_contacts'))
        return render_template('contact_form.html', contact=contact)
    else:
        if request.method == 'POST':
            new_contact = Contact(
                Name=request.form['name'],
                Club=request.form['club'],
                Date_Created=date.today(),
                Current_Project=request.form['current_project'],
                Completed_Levels=request.form['completed_levels']
            )
            db.session.add(new_contact)
            db.session.commit()
            flash('New Contact added successfully!')
            return redirect(url_for('show_contacts'))
        return render_template('contact_form.html', contact=None)

@app.route('/contact/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact deleted successfully!')
    return redirect(url_for('show_contacts'))


