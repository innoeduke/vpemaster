import re
from . import db
from .models import Contact, Achievement, Pathway, SessionLog, PathwayProject

def update_next_project(contact):
    """
    Recalculates the Next_Project for a contact based on their Current_Path,
    their current Credentials (which reflect highest Level achievements),
    and completed speech logs.
    """
    if not contact or not contact.Current_Path:
        if contact:
            contact.Next_Project = None
        return

    if contact.Current_Path == "Distinguished Toastmasters":
        contact.Next_Project = None
        return

    pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
    if not pathway or not pathway.abbr:
        return

    code_suffix = pathway.abbr
    
    # 1. Determine start_level based on credentials
    # Credentials are expected to be in format "AbbrN" e.g. "PM2"
    start_level = 1
    if contact.credentials:
        match = re.match(rf"^{code_suffix}(\d+)$", contact.credentials.strip().upper())
        if match:
            level_achieved = int(match.group(1))
            if level_achieved >= 5:
                contact.Next_Project = None
                return
            start_level = level_achieved + 1
    
    # 2. Find the first incomplete project from start_level onwards
    # Get all completed project IDs for this contact
    completed_project_ids = {
        log.Project_ID for log in SessionLog.query.filter_by(
            Owner_ID=contact.id, 
            Status='Completed'
        ).all() if log.Project_ID
    }

    for level in range(start_level, 6):
        # Query PathwayProject for this path and level, ordered by code.
        path_projects = PathwayProject.query.filter(
            PathwayProject.path_id == pathway.id,
            PathwayProject.code.like(f"{level}.%")
        ).order_by(PathwayProject.code.asc()).all()

        for pp in path_projects:
            if pp.project_id not in completed_project_ids:
                contact.Next_Project = f"{code_suffix}{pp.code}"
                return

    # If all projects in all levels are done
    contact.Next_Project = None


def sync_contact_metadata(contact_id):
    """
    Update Contact metadata (DTM, Completed_Paths, credentials, Next_Project) 
    strictly based on the Achievements table and SessionLogs.
    """
    contact = Contact.query.get(contact_id)
    if not contact:
        return None

    achievements = Achievement.query.filter_by(contact_id=contact_id).all()
    
    # 1. DTM
    is_dtm = False
    for a in achievements:
        if a.achievement_type == 'program-completion' and a.path_name == 'Distinguished Toastmasters':
            is_dtm = True
            break
    contact.DTM = is_dtm

    # 2. Completed_Paths
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
    new_credentials = None
    if contact.Current_Path:
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
            path_comp = next((a for a in achievements if a.achievement_type == 'path-completion' and a.path_name == contact.Current_Path), None)
            if path_comp:
                pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
                if pathway and pathway.abbr:
                    new_credentials = f"{pathway.abbr}5"
    
    contact.credentials = new_credentials

    # 4. Next Project
    update_next_project(contact)

    db.session.add(contact)
    db.session.commit()
    return contact
