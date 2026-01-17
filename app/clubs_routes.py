from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Club, ExComm, Contact, ContactClub
from app.auth.permissions import Permissions
from app.auth.utils import is_authorized
from datetime import datetime

clubs_bp = Blueprint('clubs_bp', __name__)

@clubs_bp.route('/clubs')
@login_required
def list_clubs():
    if not is_authorized(Permissions.CLUBS_MANAGE):
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('agenda_bp.agenda'))
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    pagination = Club.query.order_by(Club.club_no).paginate(page=page, per_page=per_page, error_out=False)
    clubs = pagination.items
    
    return render_template('clubs.html', clubs=clubs, pagination=pagination)

@clubs_bp.route('/clubs/new', methods=['GET', 'POST'])
@login_required
def create_club():
    if not is_authorized(Permissions.CLUBS_MANAGE):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('agenda_bp.agenda'))
        
    if request.method == 'POST':
        club_no = request.form.get('club_no')
        club_name = request.form.get('club_name')
        
        if not club_no or not club_name:
            flash('Club Number and Name are required.', 'danger')
            return redirect(url_for('clubs_bp.create_club'))
            
        existing_club = Club.query.filter_by(club_no=club_no).first()
        if existing_club:
            flash('Club Number already exists.', 'danger')
            return redirect(url_for('clubs_bp.create_club'))
            
        new_club = Club(
            club_no=club_no,
            club_name=club_name,
            short_name=request.form.get('short_name'),
            district=request.form.get('district'),
            division=request.form.get('division'),
            area=request.form.get('area'),
            club_address=request.form.get('club_address'),
            meeting_date=request.form.get('meeting_date'),
            contact_phone_number=request.form.get('contact_phone_number'),
            website=request.form.get('website')
        )
        
        # Handle time specific parsing if present
        meeting_time_str = request.form.get('meeting_time')
        if meeting_time_str:
            try:
                new_club.meeting_time = datetime.strptime(meeting_time_str, '%H:%M').time()
            except ValueError:
                pass # Ignore invalid time for now or handle better
        
        # Handle date specific parsing if present
        founded_date_str = request.form.get('founded_date')
        if founded_date_str:
            try:
                new_club.founded_date = datetime.strptime(founded_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        try:
            db.session.add(new_club)
            db.session.commit()
            flash('Club created successfully.', 'success')
            return redirect(url_for('clubs_bp.list_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating club: {str(e)}', 'danger')
            
    return render_template('club_form.html', title="Create New Club")

@clubs_bp.route('/clubs/<int:club_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_club(club_id):
    if not is_authorized(Permissions.CLUBS_MANAGE):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('agenda_bp.agenda'))
        
    club = db.session.get(Club, club_id)
    if not club:
        flash('Club not found.', 'danger')
        return redirect(url_for('clubs_bp.list_clubs'))
        
    if request.method == 'POST':
        club.club_no = request.form.get('club_no')
        club.club_name = request.form.get('club_name')
        club.short_name = request.form.get('short_name')
        club.district = request.form.get('district')
        club.division = request.form.get('division')
        club.area = request.form.get('area')
        club.club_address = request.form.get('club_address')
        club.meeting_date = request.form.get('meeting_date')
        club.contact_phone_number = request.form.get('contact_phone_number')
        
        website = request.form.get('website')
        if website and not (website.startswith('http://') or website.startswith('https://')):
            website = 'https://' + website
        club.website = website
        
        meeting_time_str = request.form.get('meeting_time')
        if meeting_time_str:
            try:
                club.meeting_time = datetime.strptime(meeting_time_str, '%H:%M').time()
            except ValueError:
                pass
        else:
             club.meeting_time = None
             
        founded_date_str = request.form.get('founded_date')
        if founded_date_str:
            try:
                club.founded_date = datetime.strptime(founded_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            club.founded_date = None

        try:
            db.session.commit()
            flash('Club updated successfully.', 'success')
            return redirect(url_for('clubs_bp.list_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating club: {str(e)}', 'danger')
            
    return render_template('club_form.html', title="Edit Club", club=club)

@clubs_bp.route('/clubs/<int:club_id>/delete', methods=['POST'])
@login_required
def delete_club(club_id):
    if not is_authorized(Permissions.CLUBS_MANAGE):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('agenda_bp.agenda'))
        
    club = db.session.get(Club, club_id)
    if not club:
        flash('Club not found.', 'danger')
        return redirect(url_for('clubs_bp.list_clubs'))
        
    try:
        # Find all contacts associated with this club before deleting
        associated_contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id).all()
        
        # 1. Manually delete all meetings to ensure full cleanup (Roster, SessionLogs, etc.)
        # Meeting.delete_full() handles the child items tied by meeting_number
        from .models import Meeting
        meetings = Meeting.query.filter_by(club_id=club_id).all()
        for meeting in meetings:
            success, error = meeting.delete_full()
            if not success:
                raise Exception(f"Failed to delete meeting {meeting.Meeting_Number}: {error}")
        
        # 2. Delete the club - this will cascade to UserClub and ContactClub records
        # and any other models with SQLAlchemy cascade defined
        db.session.delete(club)
        db.session.commit()
        
        # 3. Cleanup contacts that are no longer associated with any club
        # We don't delete Users, only their associated Contact records if those Records are now orphans
        for contact in associated_contacts:
            # Check if this contact still has any memberships or user associations in other clubs
            has_other_club = ContactClub.query.filter_by(contact_id=contact.id).first() is not None
            has_other_user_link = UserClub.query.filter_by(contact_id=contact.id).first() is not None
            
            if not has_other_club and not has_other_user_link:
                # This contact is truly an orphan now
                # Delete any remaining orphan data (like achievement records, which we haven't cascaded yet)
                # For safety, we can just delete the contact and rely on DB FKs or simple cleanup
                db.session.delete(contact)
        
        db.session.commit()
        flash('Club, its meetings, and its specific contacts deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting club: {str(e)}', 'danger')
        
    return redirect(url_for('clubs_bp.list_clubs'))
