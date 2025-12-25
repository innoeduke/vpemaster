
from app import create_app, db
from app.models import SessionLog, LevelRole, Presentation

app = create_app()
with app.app_context():
    def normalize(s):
        if not s: return ""
        return "".join(c for c in s if c.isalnum()).lower()

    log_id = 969
    log = SessionLog.query.get(log_id)
    if not log:
        print(f"Log {log_id} not found.")
        exit()

    print(f"--- Log {log_id} Info ---")
    
    all_presentations = Presentation.query.all()
    all_presentations_dict = {p.id: p for p in all_presentations}
    
    if log.session_type.Title == 'Presentation':
        presentation = all_presentations_dict.get(log.Project_ID)
        if presentation:
            print(f"Presentation Series: {repr(presentation.series)}")
            print(f"Normalized Series: '{normalize(presentation.series)}'")
            log.presentation_series = presentation.series
        else:
            log.presentation_series = None
    
    print("\n--- Level 4 Requirements ---")
    reqs = LevelRole.query.filter_by(level=4).all()
    for lr in reqs:
        if "Club" in lr.role or "Speaker" in lr.role:
            print(f"Req Role: {repr(lr.role)}")
            norm_target = normalize(lr.role)
            print(f"Normalized Target: '{norm_target}'")
            
            pres_series = getattr(log, 'presentation_series', None)
            norm_actual = normalize(pres_series)
            satisfied = (norm_actual == norm_target)
            print(f"Match Results: '{norm_actual}' == '{norm_target}'? {satisfied}")
