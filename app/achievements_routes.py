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
        
        db.session.commit()
        from .achievements_utils import sync_contact_metadata
        sync_contact_metadata(contact_id)

        db.session.commit()
        flash('Achievement saved successfully.', 'success')
        return redirect(url_for('achievements_bp.show_achievements'))

    contacts = Contact.query.filter(Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    
    # Categorize pathways for dynamic frontend filtering
    pathways = [p.name for p in Pathway.query.filter_by(type='pathway').order_by(Pathway.name).all()]
    programs = [p.name for p in Pathway.query.filter_by(type='program').order_by(Pathway.name).all()]
    
    project_types = ['level-completion', 'path-completion', 'program-completion']

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
    contact_id = achievement.contact_id
    db.session.delete(achievement)
    db.session.commit()
    
    from .achievements_utils import sync_contact_metadata
    sync_contact_metadata(contact_id)
    flash('Achievement deleted successfully.', 'success')
    return redirect(url_for('achievements_bp.show_achievements'))
