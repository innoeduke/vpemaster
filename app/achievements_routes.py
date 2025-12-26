from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import db
from .models import Achievement, Contact, Pathway
from .auth.utils import login_required, is_authorized
from datetime import datetime

achievements_bp = Blueprint('achievements_bp', __name__)

@achievements_bp.route('/achievements')
@login_required
def show_achievements():
    if not is_authorized('ACHIEVEMENTS_VIEW'):
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    achievements = Achievement.query.join(Contact).order_by(Achievement.issue_date.desc()).all()
    
    return render_template('achievements.html', achievements=achievements)

@achievements_bp.route('/achievement/form', defaults={'id': None}, methods=['GET', 'POST'])
@achievements_bp.route('/achievement/form/<int:id>', methods=['GET', 'POST'])
@login_required
def achievement_form(id):
    if not is_authorized('ACHIEVEMENTS_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('achievements_bp.show_achievements'))

    achievement = None
    if id:
        achievement = Achievement.query.get_or_404(id)

    if request.method == 'POST':
        contact_id = request.form.get('contact_id')
        issue_date_str = request.form.get('issue_date')
        achievement_type = request.form.get('achievement_type')
        path_name = request.form.get('path_name')
        level = request.form.get('level')
        notes = request.form.get('notes')
        member_id = None
        if contact_id:
            contact = Contact.query.get(contact_id)
            if contact:
                member_id = contact.Member_ID

        try:
            issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(request.url)

        # Check for duplicate
        # We consider a duplicate if contact, type, path, and level match.
        # Date and notes can be different (e.g. correction), but usually you don't achieve the same thing twice.
        existing_query = Achievement.query.filter_by(
            contact_id=contact_id,
            achievement_type=achievement_type,
            path_name=path_name if path_name else None,
            level=int(level) if level else None
        )
        
        if id:
            # If editing, exclude self
            existing_query = existing_query.filter(Achievement.id != id)
            
        existing = existing_query.first()
        
        if existing:
            flash('This achievement already exists for this member.', 'duplicate_warning')
            # If we are in a POST request, usually we redirect or render template.
            # If we redirect to 'request.url', we lose the form data unless we pass it back or rely on browser back.
            # But standard pattern here seems to be redirecting which resets form logic or just re-rendering.
            # Adjusting to re-render might be better to keep data, but simpler to redirect for "cancellation" as requested.
            # User said "cancelled the submission".
            return redirect(url_for('achievements_bp.show_achievements'))

        if not achievement:
            achievement = Achievement()
            db.session.add(achievement)

        achievement.contact_id = contact_id
        achievement.issue_date = issue_date
        achievement.achievement_type = achievement_type
        achievement.path_name = path_name
        achievement.level = int(level) if level else None
        achievement.notes = notes
        achievement.member_id = member_id
        
        # Update Contact.Completed_Paths if it is a path completion
        if achievement_type == 'path-completion' and path_name:
            contact = Contact.query.get(contact_id)
            if contact:
                pathway = Pathway.query.filter_by(name=path_name).first()
                if pathway and pathway.abbr:
                    abbr = pathway.abbr
                    completed_pathways = {}
                    if contact.Completed_Paths:
                        parts = contact.Completed_Paths.split('/')
                        for part in parts:
                            # Parse existing like PM5 or DL3. Assumes Abbr + Level
                            # We need to handle potential varying lengths of Abbr.
                            # Usually Abbr is 2 chars, but technically can be more.
                            # Regex is safest.
                            import re
                            match = re.match(r"([A-Z]+)(\d+)", part)
                            if match:
                                p_abbr, l_val = match.groups()
                                completed_pathways[p_abbr] = int(l_val)
                    
                    # Set level to 5 for path completion
                    completed_pathways[abbr] = 5
                    
                    new_completed_levels = [
                        f"{p}{l}" for p, l in sorted(completed_pathways.items())
                    ]
                    contact.Completed_Paths = "/".join(new_completed_levels)
                    db.session.add(contact)
        
        # Update Contact.DTM if it is a DTM achievement
        if achievement_type == 'dtm':
            contact = Contact.query.get(contact_id)
            if contact:
                contact.DTM = True
                db.session.add(contact)

        # Update Contact.credentials if it is a level completion and path is available
        if achievement_type == 'level-completion' and path_name and level:
            contact = Contact.query.get(contact_id)
            if contact:
                pathway = Pathway.query.filter_by(name=path_name).first()
                if pathway and pathway.abbr:
                    abbr = pathway.abbr
                    # Construct the new credential string, e.g. "PM1"
                    new_credential = f"{abbr}{level}"
                    
                    # Update credentials logic:
                    # If existing credentials match this path (e.g. "PM1"), update if new level is higher.
                    # If existing credentials are for a different path, just overwrite? 
                    # The requirement says "update the credentials field ... to the highest level completed for the current path".
                    # This implies we should set it to this new value. 
                    # However, purely overwriting "DL5" with "PM1" might be annoying if they want to keep the highest.
                    # But given the specific request "for the current path", it sounds like it tracks the current active path status.
                    # So let's update it. But let's check if the current credential is indeed for this path to avoid downgrading accidentally?
                    # Actually, if I just finished PM2, I want it to say PM2.
                    # If it was PM1, it becomes PM2.
                    # If it was DL5 (different path), and now I am working on PM, maybe it SHOULD become PM2?
                    # Let's assume yes, it updates to the latest achieved level for the submitted path.
                    
                    # But typically "credentials" might imply the highest *ever*. 
                    # But the user said "highest level completed *for the current path*".
                    # Let's perform a check: if the contact's Current_Path matches the path_name, we definitely update.
                    # If not, maybe we still update?
                    
                    # Actually, let's implement a safe update:
                    # 1. If credentials is empty, set it.
                    # 2. If credentials contains the same path abbr, only update if level is higher.
                    # 3. If credentials contains different path, overwrite it (assuming focus switch).
                    
                    current_cred = contact.credentials
                    should_update = True
                    
                    if current_cred:
                        import re
                        match = re.match(r"^([A-Z]+)(\d+)$", current_cred)
                        if match:
                            curr_abbr, curr_level = match.groups()
                            if curr_abbr == abbr:
                                if int(level) <= int(curr_level):
                                    should_update = False
                    
                    if should_update:
                        contact.credentials = new_credential
                        db.session.add(contact)

        db.session.commit()
        flash('Achievement saved successfully.', 'success')
        return redirect(url_for('achievements_bp.show_achievements'))

    contacts = Contact.query.filter(Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    
    # Categorize pathways for dynamic frontend filtering
    pathways = [p.name for p in Pathway.query.filter_by(type='Pathway').order_by(Pathway.name).all()]
    programs = [p.name for p in Pathway.query.filter_by(type='Program').order_by(Pathway.name).all()]
    
    project_types = ['level-completion', 'path-completion', 'program-completion', 'dtm']

    return render_template('achievement_form.html', 
                           achievement=achievement, 
                           contacts=contacts, 
                           pathways=pathways,
                           programs=programs,
                           project_types=project_types)

@achievements_bp.route('/achievement/delete/<int:id>', methods=['POST'])
@login_required
def delete_achievement(id):
    if not is_authorized('ACHIEVEMENTS_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('achievements_bp.show_achievements'))

    achievement = Achievement.query.get_or_404(id)
    db.session.delete(achievement)
    db.session.commit()
    flash('Achievement deleted successfully.', 'success')
    return redirect(url_for('achievements_bp.show_achievements'))
