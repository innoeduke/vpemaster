# vpemaster/build_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from .main_routes import login_required
from vpemaster.models import SessionLog, SessionType, Contact, Meeting
from vpemaster import db
from sqlalchemy import distinct
from datetime import datetime, timedelta
import io
import csv
import re

build_bp = Blueprint('build_bp', __name__)

@build_bp.route('/build', methods=['GET'])
@login_required
def build():
    """
    Renders the agenda builder page, displaying all session logs.
    """
    session_logs = db.session.query(SessionLog, SessionType.Is_Section).join(SessionType, SessionLog.Type_ID == SessionType.id).order_by(SessionLog.Meeting_Number.asc(), SessionLog.Meeting_Seq.asc()).all()

    # Sort meeting numbers in descending order to have the latest first
    meeting_numbers = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.desc()).all()

    session_types_query = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section} for s in session_types_query]

    contacts_query = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [{"id": c.id, "Name": c.Name} for c in contacts_query]

    message = request.args.get('message')
    category = request.args.get('category')

    return render_template('build.html',
                           logs=session_logs,
                           session_types=session_types_data,
                           contacts=contacts_data,
                           meeting_numbers=[num[0] for num in meeting_numbers],
                           message=message,
                           category=category)


@build_bp.route('/build/load', methods=['POST'])
@login_required
def load_csv():
    if 'file' not in request.files:
        return redirect(url_for('build_bp.build', message='No file part', category='error'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('build_bp.build', message='No selected file', category='error'))

    if file and file.filename.endswith('.csv'):
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)

        # 1. Process first line for meeting info
        first_line = stream.readline().strip()
        cleaned_line = re.sub(r'^\W+|\W+$', '', first_line)
        parts = cleaned_line.split(',')
        if len(parts) < 2:
            return redirect(url_for('build_bp.build', message='Invalid first line format.', category='error'))

        meeting_number, start_time_str = parts[0], parts[1]

        try:
            current_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            return redirect(url_for('build_bp.build', message='Invalid start time format in first line.', category='error'))

        meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
        if not meeting:
            meeting = Meeting(Meeting_Number=meeting_number, Start_Time=current_time)
            db.session.add(meeting)
            db.session.flush()
        else:
            meeting.Start_Time = current_time # Update start time if meeting exists

        # 2. Process subsequent rows for sessions
        csv_reader = csv.reader(stream)
        seq = 1
        for row in csv_reader:
            if not row: continue # Skip empty rows

            session_title = row[0].strip() if len(row) > 0 else ''
            owner_name = row[1].strip() if len(row) > 1 and row[1] else ''

            # 4. Match Session Type
            session_type = SessionType.query.filter_by(Title=session_title).first()
            type_id = session_type.id if session_type else 0

            # 6. Match Owner
            owner_id = None
            if owner_name:
                # Normalize whitespace by splitting and rejoining
                normalized_name = ' '.join(owner_name.split())
                owner = Contact.query.filter_by(Name=normalized_name).first()
                if owner:
                    owner_id = owner.id

            # 7. Handle Durations
            if len(row) > 3:
                duration_min = row[2].strip() if row[2] else None
                duration_max = row[3].strip() if row[3] else None
            elif len(row) > 2:
                duration_min = None
                duration_max = row[2].strip() if row[2] else None

            if not duration_max and not duration_min and session_type:
                duration_max = session_type.Duration_Max
                duration_min = session_type.Duration_Min

            # Create Session Log
            new_log = SessionLog(
                Meeting_Number=meeting_number,
                Meeting_Seq=seq,
                Type_ID=type_id,
                Owner_ID=owner_id,
                Notes=session_title, # Using Notes to store the original title
                Duration_Min=duration_min,
                Duration_Max=duration_max
            )

            # 7. Calculate Start Time for non-sections
            if session_type and not session_type.Is_Section:
                new_log.Start_Time = current_time
                # Calculate next start time
                duration_to_add = int(duration_max) if duration_max else 0
                dt_current_time = datetime.combine(datetime.today(), current_time)
                next_dt = dt_current_time + timedelta(minutes=duration_to_add + 1)
                current_time = next_dt.time()

            db.session.add(new_log)
            seq += 1

        db.session.commit()
        return redirect(url_for('build_bp.build', message='CSV file successfully loaded.', category='success'))
    else:
        return redirect(url_for('build_bp.build', message='Invalid file type. Please upload a CSV file.', category='error'))


@build_bp.route('/build/update', methods=['POST'])
@login_required
def update_logs():
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        meeting_numbers_to_update = set()

        for item in data:
            meeting_number = item.get('meeting_number')
            if not meeting_number: continue
            meeting_numbers_to_update.add(meeting_number)

            meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
            if not meeting:
                new_meeting = Meeting(Meeting_Number=meeting_number)
                db.session.add(new_meeting)
                db.session.flush()

            if item['id'] == 'new':
                new_log = SessionLog(
                    Meeting_Number=item['meeting_number'],
                    Meeting_Seq=item['meeting_seq'],
                    Type_ID=item['type_id'],
                    Owner_ID=item['owner_id'] if item['owner_id'] else None,
                    Start_Time=item['start_time'] if item['start_time'] else None,
                    Duration_Min=item['duration_min'] if item['duration_min'] else None,
                    Duration_Max=item['duration_max'] if item['duration_max'] else None,
                    Notes=item['notes']
                )
                db.session.add(new_log)
            else:
                log = SessionLog.query.get(item['id'])
                if log:
                    log.Meeting_Number = item.get('meeting_number')
                    log.Meeting_Seq = item.get('meeting_seq')
                    log.Type_ID = item.get('type_id')
                    log.Owner_ID = item.get('owner_id') if item.get('owner_id') else None
                    log.Start_Time = item.get('start_time') if item.get('start_time') else None
                    log.Duration_Min = item.get('duration_min') if item.get('duration_min') else None
                    log.Duration_Max = item.get('duration_max') if item.get('duration_max') else None
                    log.Notes = item.get('notes')

        # Recalculate start times
        for meeting_num in meeting_numbers_to_update:
            meeting = Meeting.query.filter_by(Meeting_Number=meeting_num).first()
            if not meeting or not meeting.Start_Time:
                continue

            current_time = meeting.Start_Time

            logs_to_update = db.session.query(SessionLog, SessionType.Is_Section)\
                .join(SessionType, SessionLog.Type_ID == SessionType.id)\
                .filter(SessionLog.Meeting_Number == meeting_num)\
                .order_by(SessionLog.Meeting_Seq.asc()).all()

            for log, is_section in logs_to_update:
                if not is_section:
                    log.Start_Time = current_time
                    duration_to_add = log.Duration_Max or 0
                    dt_current_time = datetime.combine(datetime.today(), current_time)
                    next_dt = dt_current_time + timedelta(minutes=duration_to_add + 1)
                    current_time = next_dt.time()
                else:
                    log.Start_Time = None

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@build_bp.route('/build/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    """
    Deletes a session log.
    """
    log = SessionLog.query.get_or_404(log_id)
    try:
        db.session.delete(log)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500