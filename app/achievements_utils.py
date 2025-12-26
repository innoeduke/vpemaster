from . import db
from .models import Contact, Achievement, Pathway

def sync_contact_metadata(contact_id):
    """
    Update Contact metadata (DTM, Completed_Paths, credentials) 
    strictly based on the Achievements table.
    """
    contact = Contact.query.get(contact_id)
    if not contact:
        return None

    achievements = Achievement.query.filter_by(contact_id=contact_id).all()
    
    # 1. DTM
    # Triggered by 'program-completion' with path 'Distinguished Toastmasters'
    is_dtm = False
    for a in achievements:
        if a.achievement_type == 'program-completion' and a.path_name == 'Distinguished Toastmasters':
            is_dtm = True
            break
    contact.DTM = is_dtm

    # 2. Completed_Paths
    # Triggered by 'path-completion'. Formatted as "Abbr5/Abbr5"
    completed_set = set()
    for a in achievements:
        if a.achievement_type == 'path-completion':
            pathway = Pathway.query.filter_by(name=a.path_name).first()
            if pathway and pathway.abbr:
                completed_set.add(f"{pathway.abbr}5")
    
    if completed_set:
        contact.Completed_Paths = "/".join(sorted(list(completed_set)))
    else:
        contact.Completed_Paths = None

    # 3. Credentials
    # Highest level achieved for the Current_Path
    new_credentials = None
    if contact.Current_Path:
        # Find all level completions for the current path
        level_achievements = [
            a for a in achievements 
            if a.achievement_type == 'level-completion' and a.path_name == contact.Current_Path and a.level
        ]
        if level_achievements:
            max_level = max(a.level for a in level_achievements)
            pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
            if pathway and pathway.abbr:
                new_credentials = f"{pathway.abbr}{max_level}"
        else:
            # If no level completions for current path, check if it's already 'path-completed'
            # (Though level 5 completion should ideally be logged as a level-completion AND path-completion)
            path_comp = next((a for a in achievements if a.achievement_type == 'path-completion' and a.path_name == contact.Current_Path), None)
            if path_comp:
                pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
                if pathway and pathway.abbr:
                    new_credentials = f"{pathway.abbr}5"

    # Fallback: if no credentials for current path, find the single highest level achievement overall?
    # User requested "highest level completed for the current path", so we stop there unless specified otherwise.
    # However, to avoid "downgrading" empty credentials if they have something significant, maybe fallback to overall max?
    # For now, let's stick to the current path logic as requested.
    
    contact.credentials = new_credentials

    db.session.add(contact)
    db.session.commit()
    return contact
