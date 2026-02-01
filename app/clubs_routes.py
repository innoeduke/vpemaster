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
    search_query = request.args.get('q', '').strip()
    
    clubs_query = Club.query
    
    if search_query:
        from sqlalchemy import or_
        clubs_query = clubs_query.filter(
            or_(
                Club.club_no.ilike(f'%{search_query}%'),
                Club.club_name.ilike(f'%{search_query}%')
            )
        )
    
    pagination = clubs_query.order_by(Club.club_no).paginate(page=page, per_page=per_page, error_out=False)
    clubs = pagination.items
    
    return render_template('clubs.html', clubs=clubs, pagination=pagination, search_query=search_query)

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
            return redirect(url_for('clubs_bp.list_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating club: {str(e)}', 'danger')
            
    return render_template('club_form.html', title="Create New Club", club=None)

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
        from .models import Meeting, UserClub
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
@clubs_bp.route('/clubs/<int:club_id>/request_home', methods=['POST'])
@login_required
def request_home(club_id):
    """
    Handles a user's request to set this club as their home club.
    Sends a message to Club Admins.
    """
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    # Check if user is a member
    from app.models import UserClub
    uc = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()
    if not uc:
        return jsonify({'success': False, 'error': 'You must be a member of the club to request it as home.'}), 400
        
    if uc.is_home:
        return jsonify({'success': False, 'error': 'This is already your home club.'}), 400

    # Identify Club Admins
    # We find users who have the SETTINGS_EDIT_ALL permission in this club
    from app.models import User, AuthRole
    from app.auth.permissions import Permissions
    
    # Get roles that have SETTINGS_EDIT_ALL
    # This loop logic is a bit manual, ideally we query simpler
    # But finding users with a permission via query is complex due to bitmask
    # Instead, let's look for known generic admin roles or rely on looping members
    
    # 1. Get all members
    members = User.query.join(UserClub).filter(UserClub.club_id == club_id).all()
    
    admins = []
    for m in members:
        if m.has_club_permission(Permissions.SETTINGS_EDIT_ALL, club_id):
            admins.append(m)
            
    if not admins:
        return jsonify({'success': False, 'error': 'No club admins found to approve your request.'}), 400
        
    # Send Message to each Admin
    from app.models import Message
    count = 0
    for admin in admins:
        # Prevent duplicates if user spams? 
        # Optional: check if pending request exists (hard via message body parsing, so maybe skip)
        
        msg = Message(
            sender_id=current_user.id,
            recipient_id=admin.id,
            subject=f"Request to set Home Club: {club.club_name}",
            body=f"User {current_user.display_name} requested to set {club.club_name} as their home club.\n\n[HOME_CLUB_REQUEST:{current_user.id}:{club_id}]"
        )
        db.session.add(msg)
        count += 1
        
    db.session.commit()
    return jsonify({'success': True, 'message': f'Request sent to {count} admins.'})


@clubs_bp.route('/clubs/respond_home_request', methods=['POST'])
@login_required
def respond_home_request():
    """
    Handles admin response (approve/reject) to a home club request.
    Payload: { message_id, action }
    """
    data = request.json
    message_id = data.get('message_id')
    action = data.get('action')
    
    from app.models import Message
    msg = db.session.get(Message, message_id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404

    # Extract info from tags
    import re
    match = re.search(r'\[HOME_CLUB_REQUEST:(\d+):(\d+)\]', msg.body)
    if not match:
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400
        
    requestor_id = int(match.group(1))
    target_club_id = int(match.group(2))
    
    # SECURITY CHECK: Verifying Admin Permission
    if not current_user.has_club_permission(Permissions.SETTINGS_EDIT_ALL, target_club_id):
        # Silent failure as requested
        return jsonify({'success': False, 'error': 'Unauthorized'}), 200
        
    from app.models import User, UserClub, Club
    requestor = db.session.get(User, requestor_id)
    target_club = db.session.get(Club, target_club_id)
    
    if not requestor or not target_club:
         return jsonify({'success': False, 'error': 'User or Club no longer exists'}), 404
         
    response_subject = f"Home Club Request: {target_club.club_name}"
    
    if action == 'approve':
        # 1. Update Home Club
        
        # Check if already home club
        existing_home_uc = UserClub.query.filter_by(user_id=requestor_id, club_id=target_club_id, is_home=True).first()
        if existing_home_uc:
            msg.read = True
            msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: ALREADY APPROVED]")
            db.session.commit()
            return jsonify({'success': False, 'error': f'{target_club.club_name} is already the Home Club for this user.'}), 400

        # Get previous home club for notification
        # Get previous home club for notification
        old_home_uc = UserClub.query.filter_by(user_id=requestor_id, is_home=True).first()
        old_home_club = old_home_uc.club if old_home_uc else None
        
        # Perform Update
        requestor.set_home_club(target_club_id)
        
        # 2. Notify User
        user_msg = Message(
            sender_id=current_user.id, # Admin
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to set **{target_club.club_name}** as your home club has been **APPROVED**."
        )
        db.session.add(user_msg)
        
        # 3. Notify Old Admin (if applicable and different club)
        if old_home_club and old_home_club.id != target_club_id:
            # Find admins of old club
            # For simplicity, finding one or broadcasting? Logic says "the clubadmin".
            # Let's broadcast to all admins found.
            old_members = User.query.join(UserClub).filter(UserClub.club_id == old_home_club.id).all()
            for m in old_members:
                if m.has_club_permission(Permissions.SETTINGS_EDIT_ALL, old_home_club.id):
                    admin_msg = Message(
                        sender_id=current_user.id,
                        recipient_id=m.id,
                        subject=f"User Changed Home Club: {requestor.display_name}",
                        body=f"User {requestor.display_name} has changed their home club from {old_home_club.club_name} to {target_club.club_name}."
                    )
                    db.session.add(admin_msg)
                    
        # Update original message
        msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: APPROVED]")
        
    elif action == 'reject':
        # Notify User
        user_msg = Message(
            sender_id=current_user.id,
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to set **{target_club.club_name}** as your home club was **REJECTED**."
        )
        db.session.add(user_msg)
        
        # Update original message
        msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: REJECTED]")
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
    msg.read = True
    db.session.commit()
    
    return jsonify({'success': True})
