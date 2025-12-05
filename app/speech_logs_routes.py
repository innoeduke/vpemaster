# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from . import db
from .models import SessionLog, Contact, Project, User, Presentation, SessionType, Media, Role, Pathway, PathwayProject
from .auth.utils import login_required, is_authorized
from .utils import project_id_to_code
from sqlalchemy import distinct
from sqlalchemy.orm import joinedload
from datetime import datetime
import re

speech_logs_bp = Blueprint('speech_logs_bp', __name__)


@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    """
    Renders the page that displays pathway project speeches.
    - Admins/Officers can filter by any speaker.
    - Members can only see their own speeches.
    """
    is_member_view = is_authorized(
        session.get('user_role'), 'SPEECH_LOGS_VIEW_OWN')

    selected_meeting = request.args.get('meeting_number')
    selected_pathway = request.args.get('pathway')
    selected_level = request.args.get('level')
    selected_speaker = request.args.get('speaker_id')
    selected_status = request.args.get('status')

    if is_member_view:
        user = User.query.get(session.get('user_id'))
        if user and user.Contact_ID:
            selected_speaker = user.Contact_ID
        else:
            selected_speaker = -1   # No logs for unlinked member

    all_pathways_from_db = Pathway.query.order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways_from_db}
    pathways = [p.name for p in all_pathways_from_db]

    # Eager load all common relationships
    base_query = db.session.query(SessionLog).options(
        joinedload(SessionLog.media),
        joinedload(SessionLog.session_type).joinedload(SessionType.role),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.owner),
        joinedload(SessionLog.project)
    ).join(SessionType).join(Role, SessionType.role_id == Role.id).filter(
        Role.name.isnot(None),
        Role.name != '',
        Role.name != 'Backup Speaker',
        # 只允许standard或club-specific类型的role
        Role.type.in_(['standard', 'club-specific'])

    )

    if selected_speaker:
        base_query = base_query.filter(SessionLog.Owner_ID == selected_speaker)
    if selected_meeting:
        base_query = base_query.filter(
            SessionLog.Meeting_Number == selected_meeting)

    all_logs = base_query.order_by(SessionLog.Meeting_Number.desc()).all()

    all_presentations = Presentation.query.order_by(
        Presentation.level, Presentation.code).all()
    all_presentations_dict = {p.id: p for p in all_presentations}

    grouped_logs = {}
    processed_roles = set()

    for log in all_logs:
        display_level = "General"  # Default bucket for roles without a level
        log_type = 'role'
        if not log.session_type or not log.session_type.role:
            continue
        role_name = log.session_type.role.name

        is_prepared_speech = log.project and log.project.Format == 'Prepared Speech'

        if log.session_type.Title == 'Presentation':
            log_type = 'presentation'
            presentation = all_presentations_dict.get(log.Project_ID)
            if presentation:
                display_level = str(presentation.level)
        elif (log.session_type.Valid_for_Project and log.Project_ID and log.Project_ID != 60) or is_prepared_speech:
            log_type = 'speech'
            path = None
            path_abbr = None
            if log.owner and log.owner.user:
                path = log.owner.user.Current_Path
                if path:
                    path_abbr = pathway_mapping.get(path)

            code = project_id_to_code(log.Project_ID, path_abbr)
            if code and len(code) > 2:
                try:
                    code_without_prefix = code[2:]
                    if '.' in code_without_prefix:
                        display_level = str(
                            int(code_without_prefix.split('.')[0]))
                    else:
                        display_level = str(
                            int(code_without_prefix.split('.')[0]))
                except (ValueError, IndexError):
                    pass

            log.project_code = code
        else:  # It's a role
            # Check if we've already processed this role for this person/meeting
            role_key = (log.Meeting_Number, log.Owner_ID, role_name)
            if role_key in processed_roles:
                continue  # Skip if already added
            processed_roles.add(role_key)  # Add to set

            # Now, get its level
            if log.current_path_level:
                match = re.match(r"[A-Z]+(\d+)", log.current_path_level)
                if match:
                    display_level = str(match.group(1))  # 确保类型一致性

        log.log_type = log_type

        if selected_level and display_level != selected_level:
            continue

        if log_type == 'speech' and selected_pathway and \
           (not log.owner or not log.owner.user or log.owner.user.Current_Path != selected_pathway):
            continue

        if selected_status:
            if log_type in ['speech', 'presentation']:
                if log.Status != selected_status:
                    continue  # Filter speeches/presentations by status
            else:
                continue  # Hide all roles if a status is selected

        # --- Add to Group ---
        if display_level not in grouped_logs:
            grouped_logs[display_level] = []
        grouped_logs[display_level].append(log)

    def get_activity_sort_key(log):
        # Failsafe, should not be needed as we assign log_type in step 3
        if not hasattr(log, 'log_type'):
            return (99, -log.Meeting_Number)

        if log.log_type == 'speech':
            priority = 1  # 1. Speeches
        elif log.log_type == 'presentation':
            priority = 2  # 2. Presentations
        else:  # 'role'
            priority = 3  # 3. Roles

        # Sort by priority (1, 2, 3), then by descending meeting number
        return (priority, -log.Meeting_Number)

    # Sort logs within each group by meeting number
    for level in grouped_logs:
        grouped_logs[level].sort(key=get_activity_sort_key)

    # Sort the groups themselves (General last)
    def get_group_sort_key(level_key):  # This part is unchanged
        if isinstance(level_key, int):
            return (0, level_key)  # Sort numbers first, by value
        return (1, level_key)  # Sort "General" string last

    sorted_grouped_logs = dict(
        sorted(grouped_logs.items(), key=lambda item: get_group_sort_key(item[0])))

    meeting_numbers = sorted([m[0] for m in db.session.query(
        distinct(SessionLog.Meeting_Number)).join(Project).all()], reverse=True)
    speakers = db.session.query(Contact).join(
        SessionLog, Contact.id == SessionLog.Owner_ID).distinct().order_by(Contact.Name).all()

    # Convert project objects to a list of dictionaries
    projects = Project.query.order_by(Project.Project_Name).all()

    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    project_codes_lookup = {}  # {project_id: {path_abbr: code, ...}}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = pp.code

    projects_data = [
        {
            "id": p.id,
            "Project_Name": p.Project_Name,
            "path_codes": project_codes_lookup.get(p.id, {}),
            "Duration_Min": p.Duration_Min,
            "Duration_Max": p.Duration_Max
        }
        for p in projects
    ]

    presentations_data = [
        {"id": p.id, "title": p.title, "level": p.level,
            "code": p.code, "series": p.series}
        for p in all_presentations
    ]
    presentation_series = sorted(
        list(set(p.series for p in all_presentations if p.series)))

    SERIES_INITIALS = current_app.config['SERIES_INITIALS']
    today_date = datetime.today().date()

    role_icons = {
        role_data['name']: role_data.get(
            'icon', current_app.config['DEFAULT_ROLE_ICON'])
        for role_data in current_app.config['ROLES'].values()
    }

    return render_template(
        'speech_logs.html',
        grouped_logs=sorted_grouped_logs,
        roles_config=current_app.config['ROLES'],
        role_icons=role_icons,
        meeting_numbers=meeting_numbers,
        speakers=speakers,
        pathways=pathways,
        levels=range(1, 6),
        projects=projects_data,  # This is used for allProjects in JS
        presentations=presentations_data,  # Pass presentation data for JS
        presentation_series=presentation_series,  # Pass series data for JS
        series_initials=SERIES_INITIALS,  # Pass initials map for template
        get_presentation_by_id=lambda pid: all_presentations_dict.get(pid),
        today_date=today_date,
        selected_filters={
            'meeting_number': selected_meeting,
            'pathway': selected_pathway,
            'level': selected_level,
            'speaker_id': selected_speaker,
            'status': selected_status
        },
        is_member_view=is_member_view,
        pathway_mapping=pathway_mapping
    )


@speech_logs_bp.route('/speech_log/details/<int:log_id>', methods=['GET'])
@login_required
def get_speech_log_details(log_id):
    """
    Fetches details for a specific speech log to populate the edit modal.
    """
    log = db.session.query(SessionLog).options(
        joinedload(SessionLog.media)).get_or_404(log_id)

    user_role = session.get('user_role')
    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None

    if not is_authorized(session.get('user_role'), 'SPEECH_LOGS_EDIT_ALL'):
        if log.Owner_ID != current_user_contact_id:
            return jsonify(success=False, message="Permission denied. You can only view details for your own speech logs."), 403

    # Use the helper function to get project code
    project_code = ""
    if log.Project_ID and log.owner and log.owner.user and log.owner.user.Current_Path:
        pathway = db.session.query(Pathway).filter_by(name=log.owner.user.Current_Path).first()
        if pathway:
            pathway_abbr = pathway.abbr
            project_code = project_id_to_code(log.Project_ID, pathway_abbr)

    level = 1  # Default level
    if project_code and project_code != "TM1.0":
        try:
            # Try to get level from codes like "PM1.1"
            # First remove the path abbreviation prefix (e.g., "PM")
            code_without_prefix = project_code[2:]  # Remove first 2 characters
            # Then extract the level number before the dot
            level = int(code_without_prefix.split('.')[0])
        except (ValueError, IndexError):
            level = 1  # Fallback if parsing fails
    # If project_code is "TM1.0" or None, level just stays 1

    pathway = log.owner.user.Current_Path if log.owner and log.owner.user and log.owner.user.Current_Path else "Presentation Mastery"

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": pathway,
        "level": level,
        "Media_URL": log.media.url if log.media else ""
    }

    return jsonify(success=True, log=log_data)


@speech_logs_bp.route('/speech_log/update/<int:log_id>', methods=['POST'])
@login_required
def update_speech_log(log_id):
    """
    Updates a speech log with new data from the edit modal.
    """
    log = db.session.query(SessionLog).options(
        joinedload(SessionLog.owner),
        joinedload(SessionLog.session_type),
        joinedload(SessionLog.project)
    ).get_or_404(log_id)

    user_role = session.get('user_role')
    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None

    if not is_authorized(session.get('user_role'), 'SPEECH_LOGS_EDIT_ALL'):
        is_owner = (user.Contact_ID == log.Owner_ID)
        if not (is_authorized(user_role, 'SPEECH_LOGS_VIEW_OWN') and is_owner):
            return jsonify(success=False, message="Permission denied. You can only edit your own speech logs."), 403

    data = request.get_json()

    session_type_title = data.get('session_type_title')
    media_url = data.get('media_url') or None

    # Pre-fetch records to avoid autoflush-related deadlocks.
    # We query for project and presentation *before* modifying the log session.
    project_id = data.get('project_id')
    updated_project = None
    presentation = None

    if project_id and project_id not in [None, "", "null"]:
        if session_type_title == 'Presentation':
            try:
                presentation = Presentation.query.get(int(project_id))
            except (ValueError, TypeError):
                pass # Gracefully handle non-integer IDs
        else:
            updated_project = Project.query.get(project_id)


    if 'session_title' in data:
        log.Session_Title = data['session_title']

    if media_url:
        # If URL is provided, update or create media record
        if log.media:
            log.media.url = media_url
        else:
            log.media = Media(url=media_url)
    elif log.media:
        # If URL is blank but a media record exists, delete it
        db.session.delete(log.media)

    # If it's a presentation and the title is *still* blank, then default to the presentation's name
    if presentation and not log.Session_Title:
        log.Session_Title = presentation.title  # Default to presentation title

    if 'pathway' in data and log.owner and log.owner.user:
        user = log.owner.user
        user.Current_Path = data['pathway']
        db.session.add(user)

    if 'project_id' in data:
        if project_id in [None, "", "null"]:
            log.Project_ID = None
        else:
            log.Project_ID = project_id

        if session_type_title == 'Presentation':
            log.Duration_Min = 10
            log.Duration_Max = 15
        elif log.Project_ID:
            if updated_project:
                log.Duration_Min = updated_project.Duration_Min
                log.Duration_Max = updated_project.Duration_Max
        else:
            # It's a generic speech, clear durations
            log.Duration_Min = None
            log.Duration_Max = None

    try:
        db.session.commit()
        project_name = "N/A"
        project_code = None
        pathway = log.owner.user.Current_Path if log.owner and log.owner.user else "N/A"

        if session_type_title == 'Presentation' and log.Project_ID:
            presentation = Presentation.query.get(log.Project_ID)
            if presentation:
                project_name = presentation.title
                pathway = presentation.series
                SERIES_INITIALS = current_app.config['SERIES_INITIALS']
                series_initial = SERIES_INITIALS.get(presentation.series, "")
                project_code = f"{series_initial}{presentation.code}"
        elif log.Project_ID:  # Pathway speech or special project
            updated_project = Project.query.get(log.Project_ID)
            if updated_project:
                project_name = updated_project.Project_Name
        # Use the helper function to get project code
            if log.owner and log.owner.user and log.owner.user.Current_Path:
                pathway_obj = db.session.query(Pathway).filter_by(name=log.owner.user.Current_Path).first()
                if pathway_obj:
                    pathway_abbr = pathway_obj.abbr
                    project_code = project_id_to_code(
                        log.Project_ID, pathway_abbr)
                    pathway = pathway_obj.name

        return jsonify(success=True,
                       session_title=log.Session_Title,
                       project_name=project_name,
                       project_code=project_code,
                       pathway=pathway,
                       project_id=log.Project_ID,
                       duration_min=log.Duration_Min,
                       duration_max=log.Duration_Max,
                       media_url=media_url)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@speech_logs_bp.route('/speech_log/suspend/<int:log_id>', methods=['POST'])
@login_required
def suspend_speech_log(log_id):
    if not is_authorized(session.get('user_role'), 'SPEECH_LOGS_EDIT_ALL'):
        return jsonify(success=False, message="Permission denied"), 403

    log = SessionLog.query.get_or_404(log_id)
    log.Status = 'Delivered'
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


def _get_next_project_for_contact(contact, completed_log):
    user = contact.user if contact else None
    if not user or not user.Current_Path or not completed_log or not completed_log.Project_ID:
        return

    pathway = db.session.query(Pathway).filter_by(name=user.Current_Path).first()
    if not pathway:
        return
    code_suffix = pathway.abbr


    pathway = db.session.query(Pathway).filter_by(abbr=code_suffix).first()
    if not pathway:
        return

    pathway_project = db.session.query(PathwayProject).filter_by(
        path_id=pathway.id, project_id=completed_log.Project_ID).first()

    if not pathway_project:
        return

    current_code = pathway_project.code

    if not current_code:
        return

    projects_per_level = {1: 3, 2: 3, 3: 3, 4: 2, 5: 3}

    try:
        level, project_num = map(int, current_code.split('.'))

        # Get all completed project IDs for this user in this pathway
        completed_project_ids = [
            log.Project_ID for log in SessionLog.query
            .join(User, SessionLog.Owner_ID == User.Contact_ID)
            .filter(User.id == user.id, User.Current_Path == user.Current_Path, SessionLog.Status == 'Completed')
            .all()
        ]

        while True:
            if project_num < projects_per_level.get(level, 0):
                project_num += 1
            else:
                project_num = 1
                level_completed = level
                level += 1

                # Smart update for Completed_Paths
                completed_pathways = {}
                if contact.Completed_Paths:
                    parts = contact.Completed_Paths.split('/')
                    for part in parts:
                        match = re.match(r"([A-Z]+)(\d+)", part)
                        if match:
                            path, l = match.groups()
                            completed_pathways[path] = int(l)

                completed_pathways[code_suffix] = level_completed

                new_completed_levels = [
                    f"{path}{lvl}" for path, lvl in sorted(completed_pathways.items())]
                contact.Completed_Paths = "/".join(new_completed_levels)

            if level > 5:
                user.Next_Project = None
                break

            next_project_code = f"{level}.{project_num}"

            next_pathway_project = db.session.query(PathwayProject).filter_by(
                path_id=pathway.id, code=next_project_code).first()

            if next_pathway_project:
                next_project = Project.query.get(
                    next_pathway_project.project_id)
            else:
                next_project = None

            if next_project and next_project.id not in completed_project_ids:
                user.Next_Project = f"{code_suffix}{next_project_code}"
                break
    except (ValueError, IndexError):
        return


@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SessionLog.query.get_or_404(log_id)

    user_role = session.get('user_role')
    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None

    if not is_authorized(session.get('user_role'), 'SPEECH_LOGS_EDIT_ALL'):
        if log.Owner_ID != current_user_contact_id:
            return jsonify(success=False, message="Permission denied."), 403
        # Also check if meeting is in the past for non-admins
        if log.meeting and log.meeting.Meeting_Date and log.meeting.Meeting_Date >= datetime.today().date():
            return jsonify(success=False, message="You can only complete logs for past meetings."), 403

    log.Status = 'Completed'

    if log.Owner_ID:
        contact = Contact.query.get(log.Owner_ID)
        _get_next_project_for_contact(contact, log)

    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
