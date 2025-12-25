
from app import create_app, db
from app.models import SessionLog, LevelRole, Presentation, SessionType, Role, Project

app = create_app()
with app.app_context():
    def normalize(s):
        return s.replace(' ', '').replace('-', '').lower()

    log_id = 969
    log = SessionLog.query.get(log_id)
    if not log:
        print(f"Log {log_id} not found.")
        exit()

    print(f"--- Log {log_id} Info ---")
    print(f"Title: '{log.Session_Title}'")
    print(f"Project_ID: {log.Project_ID}")
    session_type_title = log.session_type.Title if log.session_type else "N/A"
    print(f"SessionType Title: '{session_type_title}'")
    
    # Replicate log processing logic from show_speech_logs
    log_type = 'role'
    display_level = "General"
    
    all_presentations = Presentation.query.all()
    all_presentations_dict = {p.id: p for p in all_presentations}
    
    if log.session_type.Title == 'Presentation':
        log_type = 'presentation'
        presentation = all_presentations_dict.get(log.Project_ID)
        if presentation:
            display_level = str(presentation.level)
            log.presentation_series = presentation.series
            print(f"Presentation Found: Title='{presentation.title}', Level={presentation.level}, Series='{presentation.series}'")
        else:
            print("Presentation NOT found in all_presentations_dict")
            log.presentation_series = None
    
    log.log_type = log_type
    print(f"Assigned log_type: '{log.log_type}', display_level: '{display_level}'")

    print("\n--- Level 4 Requirements ---")
    reqs = LevelRole.query.filter_by(level=4).all()
    for lr in reqs:
        target_role_name = lr.role.strip().lower()
        norm_target = normalize(target_role_name)
        
        satisfied = False
        actual_role_name = (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "")).strip().lower()
        norm_actual = normalize(actual_role_name)
        
        is_role_match = (norm_actual == norm_target)
        if not is_role_match:
            aliases = {'topicmaster': 'topicsmaster', 'topicsmaster': 'topicmaster', 'tme': 'toastmaster', 'toastmaster': 'tme', 'ge': 'generalevaluator', 'generalevaluator': 'ge'}
            if aliases.get(norm_actual) == norm_target:
                is_role_match = True

        if is_role_match:
            satisfied = True
        elif log.log_type == 'presentation':
            pres_series = getattr(log, 'presentation_series', None)
            if lr.role.lower() == 'presentation':
                satisfied = True
            elif pres_series and normalize(pres_series) == norm_target:
                satisfied = True
        
        print(f"Req: '{lr.role}', NormTarget: '{norm_target}', Satisfied: {satisfied}")
