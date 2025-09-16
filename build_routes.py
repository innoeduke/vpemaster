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
    session_logs = db.session.query(SessionLog, SessionType.Is_Section).join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True).order_by(SessionLog.Meeting_Number.asc(), SessionLog.Meeting_Seq.asc()).all()

    # Sort meeting numbers in descending order to have the latest first
    meeting_numbers = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.desc()).all()

    session_types_query = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section} for s in session_types_query]

    contacts_query = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [{"id": c.id, "Name": c.Name} for c in contacts_query]

    return render_template('build.html',
                           logs=session_logs,
                           session_types=session_types_data,
                           contacts=contacts_data,
                           meeting_numbers=[num[0] for num in meeting_numbers])


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

            session_title_from_csv = row[0].strip() if len(row) > 0 else ''
            owner_name = row[1].strip() if len(row) > 1 and row[1] else ''

            # 4. Match Session Type
            session_type = SessionType.query.filter_by(Title=session_title_from_csv).first()
            type_id = session_type.id if session_type else 0

            session_title = session_type.Title if session_type else session_title_from_csv


            # 6. Match Owner
            owner_id = None
            if owner_name:
                # Normalize whitespace by splitting and rejoining
                normalized_name = ' '.join(owner_name.split())
                owner = Contact.query.filter_by(Name=normalized_name).first()
                if owner:
                    owner_id = owner.id

            # 7. Handle Durations
            duration_min, duration_max = None, None
            if len(row) > 3:
                duration_min = row[2].strip() if row[2] else None
                duration_max = row[3].strip() if row[3] else None
            elif len(row) > 2:
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
                Session_Title=session_title,
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
        return redirect(url_for('build_bp.build'))
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
        items_by_meeting = {}

        for item in data:
            meeting_number = item.get('meeting_number')
            if not meeting_number:
                continue
            meeting_numbers_to_update.add(meeting_number)
            if meeting_number not in items_by_meeting:
                items_by_meeting[meeting_number] = []
            items_by_meeting[meeting_number].append(item)

        for meeting_number, items in items_by_meeting.items():
            # Get original sequences for tie-breaking
            original_logs = SessionLog.query.filter_by(Meeting_Number=meeting_number).all()
            original_seqs = {log.id: log.Meeting_Seq for log in original_logs}

            # Define a custom sort key to handle re-ordering
            def sort_key(item):
                new_seq = int(item.get('meeting_seq', 999))
                item_id_str = item.get('id')
                priority = 0
                if item_id_str == 'new':
                    priority = 0
                else:
                    try:
                        item_id = int(item_id_str)
                        original_seq = original_seqs.get(item_id)
                        if original_seq == new_seq:
                            priority = 2
                        else:
                            priority = 1
                    except (ValueError, TypeError):
                        # This will handle cases where item_id is not a valid integer
                        priority = 0

                return (new_seq, priority)

            # Sort items by the new sequence number, with our priority tie-breaking
            sorted_items = sorted(items, key=sort_key)

            for seq, item in enumerate(sorted_items, 1):
                meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
                if not meeting:
                    new_meeting = Meeting(Meeting_Number=meeting_number)
                    db.session.add(new_meeting)
                    db.session.flush()
                    meeting = new_meeting

                if seq == 1 and item.get('start_time'):
                    try:
                        meeting.Start_Time = datetime.strptime(item.get('start_time'), '%H:%M:%S').time()
                    except ValueError:
                        meeting.Start_Time = datetime.strptime(item.get('start_time'), '%H:%M').time()

                type_id = item.get('type_id')
                session_type = SessionType.query.get(type_id)
                session_title = item.get('session_title')

                if item['id'] == 'new':
                    if not session_title and session_type:
                        session_title = session_type.Title
                    new_log = SessionLog(
                        Meeting_Number=meeting_number,
                        Meeting_Seq=seq,
                        Type_ID=type_id,
                        Owner_ID=item['owner_id'] if item['owner_id'] else None,
                        Duration_Min=item['duration_min'] if item['duration_min'] else None,
                        Duration_Max=item['duration_max'] if item['duration_max'] else None,
                        Session_Title=session_title
                    )
                    db.session.add(new_log)
                else:
                    log = SessionLog.query.get(item['id'])
                    if log:
                        log.Meeting_Number = meeting_number
                        log.Meeting_Seq = seq
                        log.Type_ID = type_id
                        log.Owner_ID = item.get('owner_id') if item.get('owner_id') else None
                        log.Duration_Min = item.get('duration_min') if item.get('duration_min') else None
                        log.Duration_Max = item.get('duration_max') if item.get('duration_max') else None

                        if session_title:
                            log.Session_Title = session_title
                        elif session_type:
                            log.Session_Title = session_type.Title
                        else:
                            log.Session_Title = ''


        # Recalculate start times
        for meeting_num in meeting_numbers_to_update:
            meeting = Meeting.query.filter_by(Meeting_Number=meeting_num).first()
            if not meeting or not meeting.Start_Time:
                continue

            current_time = meeting.Start_Time

            logs_to_update = db.session.query(SessionLog, SessionType.Is_Section)\
                .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
                .filter(SessionLog.Meeting_Number == meeting_num)\
                .order_by(SessionLog.Meeting_Seq.asc()).all()

            for log, is_section in logs_to_update:
                if not is_section:
                    log.Start_Time = current_time
                    duration_to_add = int(log.Duration_Max or 0)
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