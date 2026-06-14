from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import db
from app.models import Club, ExComm, Contact, ContactClub
from app.auth.permissions import Permissions
from app.auth.utils import is_authorized
from datetime import datetime
import os
import shutil

clubs_bp = Blueprint('clubs_bp', __name__)


@clubs_bp.before_request
def check_club_directory_enabled():
    # Allow enter_club route to bypass check
    if request.endpoint and (request.endpoint.endswith('.enter_club') or request.endpoint.endswith('.enter')):
        return

    from flask import g
    # Flag that we're on the directory so the global context processor
    # doesn't auto-restore a default club and re-disable the Enter button.
    g.in_club_directory = True

    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Club Directory'):
        abort(404)

class MemoryPagination:
    def __init__(self, items, page, per_page):
        self.total = len(items)
        self.page = page
        self.per_page = per_page
        
        # Calculate total pages
        self.pages = (self.total + per_page - 1) // per_page if self.total > 0 else 1
        
        # Clamp page range
        if self.page < 1:
            self.page = 1
        elif self.page > self.pages:
            self.page = self.pages
            
        start_idx = (self.page - 1) * per_page
        end_idx = start_idx + per_page
        self.items = items[start_idx:end_idx]
        
    @property
    def has_prev(self):
        return self.page > 1
        
    @property
    def has_next(self):
        return self.page < self.pages
        
    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None
        
    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None


@clubs_bp.route('/clubs')
def list_clubs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)
    search_query = request.args.get('q', '').strip()

    # Visiting the directory means stepping out of any active club context,
    # so the current-club card renders with an active Enter button again.
    session.pop('current_club_id', None)

    # 1. Fetch all clubs and filter in python (or database where status != 'super')
    # Filter out super clubs (Technical Support)
    clubs_query = Club.query.filter(Club.status != 'super')
    
    if search_query:
        from sqlalchemy import or_
        clubs_query = clubs_query.filter(
            or_(
                Club.club_no.ilike(f'%{search_query}%'),
                Club.club_name.ilike(f'%{search_query}%'),
                Club.short_name.ilike(f'%{search_query}%')
            )
        )
        
    all_visible_clubs = clubs_query.all()
    
    # 2. Fetch next meeting info for visible clubs
    from app.models import Meeting
    from datetime import datetime
    
    club_ids = [c.id for c in all_visible_clubs]
    next_meetings = []
    if club_ids:
        next_meetings = Meeting.query.filter(
            Meeting.club_id.in_(club_ids),
            Meeting.Meeting_Date >= datetime.now().date(),
            Meeting.status != 'cancelled'
        ).order_by(Meeting.Meeting_Date.asc()).all()
        
    next_meeting_by_club = {}
    for m in next_meetings:
        if m.club_id not in next_meeting_by_club:
            next_meeting_by_club[m.club_id] = m
            
    # 3. Retrieve user state (memberships, home club, favorites)
    from app.models import UserClub
    user_memberships = {}
    user_favorites = set()
    home_club_id = None
    
    if current_user.is_authenticated:
        for membership in current_user.club_memberships:
            # A UserClub with role 'Guest' is a guest-visit record, not a
            # membership — it must not appear in user_memberships and must
            # not qualify the club as the user's home club.
            if membership.auth_role and membership.auth_role.name == 'Guest':
                continue
            user_memberships[membership.club_id] = membership
            if membership.is_home:
                home_club_id = membership.club_id
        user_favorites = {c.id for c in current_user.favorite_clubs.all()}
        
    # 4. Sorting logic
    # - Home club (first & highlighted)
    # - Joined clubs
    # - Favorite clubs
    # - Other clubs
    # Sub-ordered by next meeting date (earliest first, no-meeting clubs last).
    from datetime import date
    
    def get_sort_key(c):
        if c.id == home_club_id:
            category = 0
        elif c.id in user_memberships:
            category = 1
        elif c.id in user_favorites:
            category = 2
        else:
            category = 3
            
        next_meeting = next_meeting_by_club.get(c.id)
        meeting_date = next_meeting.Meeting_Date if next_meeting else None
        
        sort_date = meeting_date if meeting_date else date.max
        return (category, sort_date, c.club_name or '')
        
    all_visible_clubs.sort(key=get_sort_key)
    
    # 5. Paginate in memory
    pagination = MemoryPagination(all_visible_clubs, page, per_page)
    clubs = pagination.items
    
    # 6. Retrieve pending join & quit requests
    pending_club_ids = []
    pending_quit_club_ids = []
    if current_user.is_authenticated:
        from app.models import Message
        import re
        
        pending_messages = Message.query.filter(
            Message.sender_id == current_user.id,
            Message.body.like(f"%[JOIN_REQUEST:{current_user.id}:%")
        ).all()
        for msg in pending_messages:
            match = re.search(r'\[JOIN_REQUEST:\d+:(\d+)\]', msg.body)
            if match and "[Responded:" not in msg.body:
                pending_club_ids.append(int(match.group(1)))
                
        pending_quit_messages = Message.query.filter(
            Message.sender_id == current_user.id,
            Message.body.like(f"%[QUIT_REQUEST:{current_user.id}:%")
        ).all()
        for msg in pending_quit_messages:
            match = re.search(r'\[QUIT_REQUEST:\d+:(\d+)\]', msg.body)
            if match and "[Responded:" not in msg.body:
                pending_quit_club_ids.append(int(match.group(1)))
                
    return render_template(
        'clubs.html',
        clubs=clubs,
        pagination=pagination,
        search_query=search_query,
        pending_club_ids=pending_club_ids,
        pending_quit_club_ids=pending_quit_club_ids,
        user_memberships=user_memberships,
        user_favorites=user_favorites,
        home_club_id=home_club_id,
        next_meeting_by_club=next_meeting_by_club
    )

@clubs_bp.route('/clubs/new', methods=['GET', 'POST'])
@login_required
def create_club():
    if not is_authorized(Permissions.SETTINGS_EDIT):
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
            
            # Initialize modules as disabled
            from app.models.club_module import ClubModule
            ClubModule.initialize_club_modules(new_club.id)
            db.session.commit()
            
            # Seed club resources
            from flask import current_app
            src_dir = os.path.join(current_app.static_folder, 'club_resources', '0')
            dst_dir = os.path.join(current_app.static_folder, 'club_resources', str(new_club.id))
            
            if os.path.exists(src_dir) and not os.path.exists(dst_dir):
                shutil.copytree(src_dir, dst_dir)
            
            # Set default logo to the copied file
            new_club.logo_url = f'club_resources/{new_club.id}/club_logo.webp'
            db.session.commit()

            return redirect(url_for('clubs_bp.list_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating club: {str(e)}', 'danger')
            
    return render_template('club_form.html', title="Create New Club", club=None)

@clubs_bp.route('/clubs/<int:club_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_club(club_id):
    if not is_authorized(Permissions.SETTINGS_EDIT):
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
    if not is_authorized(Permissions.SETTINGS_EDIT):
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

        # 4. Delete the club's resource folder
        from flask import current_app
        resource_dir = os.path.join(current_app.static_folder, 'club_resources', str(club_id))
        if os.path.exists(resource_dir):
            shutil.rmtree(resource_dir)

        flash('Club, its meetings, its specific contacts, and its resource folder deleted successfully.', 'success')
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

    # If the user IS a club admin, approve immediately
    from app.auth.permissions import Permissions
    if current_user.has_club_permission(Permissions.SETTINGS_EDIT, club_id):
        current_user.set_home_club(club_id)
        return jsonify({'success': True, 'message': f'{club.club_name} has been set as your home club.'})

    # Identify Club Admins
    # We find users who have the SETTINGS_EDIT_ALL permission in this club
    from app.models import User
    
    # 1. Get all members
    members = User.query.join(UserClub).filter(UserClub.club_id == club_id).all()
    
    admins = []
    for m in members:
        if m.has_club_permission(Permissions.SETTINGS_EDIT, club_id):
            admins.append(m)
            
    if not admins:
        return jsonify({'success': False, 'error': f'No club admin was found for {club.club_name} to approve your request. Please contact your club leadership.'}), 400
        
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
    if not current_user.has_club_permission(Permissions.SETTINGS_EDIT, target_club_id):
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
                if m.has_club_permission(Permissions.SETTINGS_EDIT, old_home_club.id):
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


@clubs_bp.route('/clubs/respond_home_proposal', methods=['POST'])
@login_required
def respond_home_proposal():
    """
    Handles user response (approve/reject) to an admin's home club proposal.
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
    match = re.search(r'\[HOME_CLUB_PROPOSAL:(\d+):(\d+)\]', msg.body)
    if not match:
        return jsonify({'success': False, 'error': 'Invalid proposal format'}), 400
        
    admin_id = int(match.group(1))
    target_club_id = int(match.group(2))
    
    # SECURITY CHECK: Only the recipient can approve the proposal
    if msg.recipient_id != current_user.id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    from app.models import User, Club
    target_club = db.session.get(Club, target_club_id) if target_club_id != 0 else None
    
    response_subject = f"Response to Home Club Proposal: {target_club.club_name if target_club else 'None'}"
    
    if action == 'approve':
        # 1. Update Home Club
        current_user.set_home_club(target_club_id if target_club_id != 0 else None)
        
        # 2. Notify Admin
        admin_msg = Message(
            sender_id=current_user.id,
            recipient_id=admin_id,
            subject=response_subject,
            body=f"User {current_user.display_name} has **APPROVED** your proposal to set **{target_club.club_name if target_club else 'None'}** as their home club."
        )
        db.session.add(admin_msg)
        
        # Update original message
        msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: APPROVED]")
        
    elif action == 'reject':
        # Notify Admin
        admin_msg = Message(
            sender_id=current_user.id,
            recipient_id=admin_id,
            subject=response_subject,
            body=f"User {current_user.display_name} has **REJECTED** your proposal to set **{target_club.club_name if target_club else 'None'}** as their home club."
        )
        db.session.add(admin_msg)
        
        # Update original message
        msg.body = msg.body.replace(match.group(0), f"\n\n[Responded: REJECTED]")
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
    msg.read = True
    db.session.commit()
    
    return jsonify({'success': True})


@clubs_bp.route('/clubs/<int:club_id>/request_join', methods=['POST'])
@login_required
def request_join_club(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    # Check if already a member
    from app.models import UserClub
    uc = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()
    if uc:
        return jsonify({'success': False, 'error': 'You are already a member of this club.'}), 400
        
    # Check if a pending request already exists
    from app.models import Message
    existing = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.body.like(f"%[JOIN_REQUEST:{current_user.id}:{club_id}]%"),
        ~Message.body.like("%[Responded:%")
    ).first()
    if existing:
        return jsonify({'success': False, 'error': 'You already have a pending join request for this club.'}), 400

    # Identify Club Admins
    from app.models import User
    members = User.query.join(UserClub).filter(UserClub.club_id == club_id).all()
    admins = [m for m in members if m.has_club_permission(Permissions.SETTINGS_EDIT, club_id)]
    
    if not admins:
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if sysadmin:
            admins = [sysadmin]
            
    if not admins:
        return jsonify({'success': False, 'error': 'No club administrator found to approve your request.'}), 400
        
    # Send Join Request message to all admins of the club
    for admin in admins:
        msg = Message(
            sender_id=current_user.id,
            recipient_id=admin.id,
            subject=f"Join Request: {club.club_name} from {current_user.display_name}",
            body=f"User {current_user.display_name} ({current_user.email or current_user.username}) has requested to join {club.club_name} as a member.\n\n[JOIN_REQUEST:{current_user.id}:{club_id}]"
        )
        db.session.add(msg)
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Your request to join the club has been sent.'})


@clubs_bp.route('/clubs/respond_join_request', methods=['POST'])
@login_required
def respond_join_request():
    data = request.json
    message_id = data.get('message_id')
    action = data.get('action')
    
    from app.models import Message
    msg = db.session.get(Message, message_id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
        
    import re
    match = re.search(r'\[JOIN_REQUEST:(\d+):(\d+)\]', msg.body)
    if not match:
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400
        
    requestor_id = int(match.group(1))
    target_club_id = int(match.group(2))
    
    # Check if current user is authorized to manage settings for this club
    if not current_user.has_club_permission(Permissions.SETTINGS_EDIT, target_club_id) and not current_user.is_sysadmin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    from app.models import User, Club, UserClub
    requestor = db.session.get(User, requestor_id)
    target_club = db.session.get(Club, target_club_id)
    
    if not requestor or not target_club:
        return jsonify({'success': False, 'error': 'User or Club no longer exists'}), 404
        
    response_subject = f"Join Request Response: {target_club.club_name}"
    
    if action == 'approve':
        # Check if already a member
        uc = UserClub.query.filter_by(user_id=requestor_id, club_id=target_club_id).first()
        if not uc:
            requestor.ensure_contact(club_id=target_club_id)
            from app.models import AuthRole
            user_role = AuthRole.query.filter_by(name='Member').first()
            requestor.set_club_role(target_club_id, role_id=user_role.id if user_role else None)
            
        # Send message to user
        reply = Message(
            sender_id=current_user.id,
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to join **{target_club.club_name}** has been **APPROVED**."
        )
        db.session.add(reply)
        
    elif action == 'reject':
        reply = Message(
            sender_id=current_user.id,
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to join **{target_club.club_name}** was **REJECTED**."
        )
        db.session.add(reply)
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
    # Mark all duplicate join messages as responded & read to avoid cluttering other admins' inboxes
    all_related_msgs = Message.query.filter(
        Message.body.like(f"%[JOIN_REQUEST:{requestor_id}:{target_club_id}]%")
    ).all()
    action_text = 'APPROVED' if action == 'approve' else 'REJECTED'
    for m in all_related_msgs:
        m.body = re.sub(r'\[JOIN_REQUEST:\d+:\d+\]', f"\n\n[Responded: {action_text}]", m.body)
        m.read = True
        
    db.session.commit()
    return jsonify({'success': True})


@clubs_bp.route('/clubs/<int:club_id>/request_quit', methods=['POST'])
@login_required
def request_quit_club(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    # Check if a member
    from app.models import UserClub
    uc = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()
    if not uc:
        return jsonify({'success': False, 'error': 'You are not a member of this club.'}), 400
        
    # Check if a pending quit request already exists
    from app.models import Message
    import re
    existing = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.body.like(f"%[QUIT_REQUEST:{current_user.id}:{club_id}]%"),
        ~Message.body.like("%[Responded:%")
    ).first()
    if existing:
        return jsonify({'success': False, 'error': 'You already have a pending quit request for this club.'}), 400

    # Identify Club Admins
    from app.models import User
    members = User.query.join(UserClub).filter(UserClub.club_id == club_id).all()
    admins = [m for m in members if m.has_club_permission(Permissions.SETTINGS_EDIT, club_id)]
    
    if not admins:
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if sysadmin:
            admins = [sysadmin]
            
    if not admins:
        return jsonify({'success': False, 'error': 'No club administrator found to approve your request.'}), 400
        
    # Send Quit Request message to all admins of the club
    for admin in admins:
        msg = Message(
            sender_id=current_user.id,
            recipient_id=admin.id,
            subject=f"Quit Request: {club.club_name} from {current_user.display_name}",
            body=f"User {current_user.display_name} ({current_user.email or current_user.username}) has requested to leave {club.club_name}.\n\n[QUIT_REQUEST:{current_user.id}:{club_id}]"
        )
        db.session.add(msg)
        
    db.session.commit()
    return jsonify({'success': True, 'message': 'Your request to leave the club has been sent.'})


@clubs_bp.route('/clubs/respond_quit_request', methods=['POST'])
@login_required
def respond_quit_request():
    data = request.json
    message_id = data.get('message_id')
    action = data.get('action')
    
    from app.models import Message
    msg = db.session.get(Message, message_id)
    if not msg:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
        
    import re
    match = re.search(r'\[QUIT_REQUEST:(\d+):(\d+)\]', msg.body)
    if not match:
        return jsonify({'success': False, 'error': 'Invalid request format'}), 400
        
    requestor_id = int(match.group(1))
    target_club_id = int(match.group(2))
    
    # Check if current user is authorized to manage settings for this club
    if not current_user.has_club_permission(Permissions.SETTINGS_EDIT, target_club_id) and not current_user.is_sysadmin:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    from app.models import User, Club, UserClub
    requestor = db.session.get(User, requestor_id)
    target_club = db.session.get(Club, target_club_id)
    
    if not requestor or not target_club:
        return jsonify({'success': False, 'error': 'User or Club no longer exists'}), 404
        
    response_subject = f"Quit Request Response: {target_club.club_name}"
    
    if action == 'approve':
        # Check if they are a member
        uc = UserClub.query.filter_by(user_id=requestor_id, club_id=target_club_id).first()
        if uc:
            is_home = uc.is_home
            db.session.delete(uc)
            
            # If they quit their home club, make another club home if they have any remaining memberships
            if is_home:
                db.session.flush() # Flush deletion
                remaining_uc = UserClub.query.filter_by(user_id=requestor_id).first()
                if remaining_uc:
                    remaining_uc.is_home = True
            
        # Send message to user
        reply = Message(
            sender_id=current_user.id,
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to leave **{target_club.club_name}** has been **APPROVED**."
        )
        db.session.add(reply)
        
    elif action == 'reject':
        reply = Message(
            sender_id=current_user.id,
            recipient_id=requestor_id,
            subject=response_subject,
            body=f"Your request to leave **{target_club.club_name}** was **REJECTED**."
        )
        db.session.add(reply)
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
    # Mark all duplicate quit messages as responded & read
    all_related_msgs = Message.query.filter(
        Message.body.like(f"%[QUIT_REQUEST:{requestor_id}:{target_club_id}]%")
    ).all()
    action_text = 'APPROVED' if action == 'approve' else 'REJECTED'
    for m in all_related_msgs:
        m.body = re.sub(r'\[QUIT_REQUEST:\d+:\d+\]', f"\n\n[Responded: {action_text}]", m.body)
        m.read = True
        
    db.session.commit()
    return jsonify({'success': True})


@clubs_bp.route('/clubs/<int:club_id>/favorite', methods=['POST'])
@login_required
def favorite_club(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    is_favorite = False
    if club in current_user.favorite_clubs.all():
        current_user.favorite_clubs.remove(club)
    else:
        current_user.favorite_clubs.append(club)
        is_favorite = True
        
    db.session.commit()
    return jsonify({
        'success': True,
        'is_favorite': is_favorite,
        'message': 'Club followed.' if is_favorite else 'Club unfollowed.'
    })


@clubs_bp.route('/clubs/<int:club_id>/enter', methods=['POST'])
def enter_club(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404

    # Only create a UserClub record for logged-in users. Guests browse without
    # a stored membership — the session-stored club context is all that's needed.
    if current_user.is_authenticated:
        from app.models import UserClub
        uc = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()
        if not uc:
            # User is not a member, so they take the Guest role
            from app.models import AuthRole
            guest_role = AuthRole.query.filter_by(name='Guest').first()
            if not guest_role:
                return jsonify({'success': False, 'error': 'Guest role not found in system.'}), 500

            # Create a UserClub record with Guest role
            current_user.ensure_contact(club_id=club_id)
            current_user.set_club_role(club_id, role_id=guest_role.id)
            db.session.commit()

    # Set current club context in session
    from app.club_context import set_current_club_id
    set_current_club_id(club_id)

    return jsonify({'success': True, 'redirect_url': url_for('agenda_bp.agenda')})


@clubs_bp.route('/clubs/<int:club_id>/cancel_join', methods=['POST'])
@login_required
def cancel_join_request(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    from app.models import Message
    import re

    # Find related messages sent by this user for this club
    related_msgs = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.body.like(f"%[JOIN_REQUEST:{current_user.id}:{club_id}]%")
    ).all()

    if not related_msgs:
        return jsonify({'success': False, 'error': 'No pending join request found for this club.'}), 400

    count = 0
    for m in related_msgs:
        if "[Responded:" not in m.body:
            m.body = re.sub(r'\[JOIN_REQUEST:\d+:\d+\]', "\n\n[Responded: CANCELLED]", m.body)
            m.read = True
            count += 1

    if count == 0:
        return jsonify({'success': False, 'error': 'Your request has already been processed.'}), 400

    db.session.commit()
    return jsonify({'success': True, 'message': 'Your join request has been cancelled.'})


@clubs_bp.route('/clubs/<int:club_id>/cancel_quit', methods=['POST'])
@login_required
def cancel_quit_request(club_id):
    club = db.session.get(Club, club_id)
    if not club:
        return jsonify({'success': False, 'error': 'Club not found'}), 404
        
    from app.models import Message
    import re

    # Find related messages sent by this user for this club
    related_msgs = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.body.like(f"%[QUIT_REQUEST:{current_user.id}:{club_id}]%")
    ).all()

    if not related_msgs:
        return jsonify({'success': False, 'error': 'No pending quit request found for this club.'}), 400

    count = 0
    for m in related_msgs:
        if "[Responded:" not in m.body:
            m.body = re.sub(r'\[QUIT_REQUEST:\d+:\d+\]', "\n\n[Responded: CANCELLED]", m.body)
            m.read = True
            count += 1

    if count == 0:
        return jsonify({'success': False, 'error': 'Your request has already been processed.'}), 400

    db.session.commit()
    return jsonify({'success': True, 'message': 'Your quit request has been cancelled.'})


