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
        member_id = request.form.get('member_id')

        try:
            issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'error')
            return redirect(request.url)

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
        flash('Achievement saved successfully.', 'success')
        return redirect(url_for('achievements_bp.show_achievements'))

    contacts = Contact.query.filter(Contact.Type.in_(['Member', 'Officer'])).order_by(Contact.Name.asc()).all()
    pathways = [p.name for p in Pathway.query.filter(Pathway.type.in_(['Pathway', 'Program'])).order_by(Pathway.type, Pathway.name).all()]
    project_types = ['level-completion', 'path-completion', 'program-completion', 'dtm']

    return render_template('achievement_form.html', 
                           achievement=achievement, 
                           contacts=contacts, 
                           pathways=pathways,
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
