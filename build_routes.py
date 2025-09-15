# vpemaster/build_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from .main_routes import login_required
from vpemaster.models import SessionLog, SessionType, Contact, Meeting
from vpemaster import db
from sqlalchemy import distinct

build_bp = Blueprint('build_bp', __name__)

@build_bp.route('/build', methods=['GET', 'POST'])
@login_required
def build():
    """
    Renders the agenda builder page, displaying all session logs
    and handles adding new logs.
    """
    if request.method == 'POST':
        meeting_number = request.form.get('meeting_number')

        meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
        if not meeting:
            new_meeting = Meeting(Meeting_Number=meeting_number)
            db.session.add(new_meeting)
            db.session.flush() # Ensure meeting is created before log is added

        owner_id = request.form.get('owner_id')
        duration_min = request.form.get('duration_min')
        duration_max = request.form.get('duration_max')
        start_time = request.form.get('start_time')

        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Type_ID=request.form.get('type_id'),
            Owner_ID=int(owner_id) if owner_id else None,
            Start_Time=start_time if start_time else None,
            Duration_Min=int(duration_min) if duration_min else None,
            Duration_Max=int(duration_max) if duration_max else None,
            Meeting_Seq=request.form.get('meeting_seq'),
            Notes=request.form.get('notes')
        )
        db.session.add(new_log)
        db.session.commit()
        return redirect(url_for('build_bp.build'))

    # Join SessionLog with SessionType to access the Is_Section flag
    session_logs = db.session.query(SessionLog, SessionType.Is_Section).join(SessionType, SessionLog.Type_ID == SessionType.id).order_by(SessionLog.Meeting_Number.asc(), SessionLog.Meeting_Seq.asc()).all()

    meeting_numbers = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.asc()).all()

    # Convert SQLAlchemy objects to a list of dictionaries to be JSON serializable
    session_types_query = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section} for s in session_types_query]

    contacts_query = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [{"id": c.id, "Name": c.Name} for c in contacts_query]

    return render_template('build.html',
                           logs=session_logs,
                           session_types=session_types_data,
                           contacts=contacts_data,
                           meeting_numbers=[num[0] for num in meeting_numbers])


@build_bp.route('/build/update', methods=['POST'])
@login_required
def update_logs():
    """
    Updates or creates session logs from the editable table.
    """
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            meeting_number = item.get('meeting_number')
            if not meeting_number:
                continue

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