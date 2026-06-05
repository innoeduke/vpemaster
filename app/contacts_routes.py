# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
import urllib.parse
from . import db
from .models import Contact, SessionLog, Pathway, ContactClub, Meeting, Vote, ExComm, UserClub, Roster, SessionType, MeetingRole, OwnerMeetingRoles, Club
from .auth.utils import login_required, is_authorized, club_permission_required
from .auth.permissions import Permissions
from .club_context import get_current_club_id, authorized_club_required
from flask_login import current_user
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from datetime import date, timedelta

contacts_bp = Blueprint('contacts_bp', __name__)


@contacts_bp.route('/contacts/search')
@login_required
@authorized_club_required
def search_contacts_by_name():
    search_term = request.args.get('q', '')
    club_id = get_current_club_id()
    query = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)
    
    # Permission filtering
    if not is_authorized(Permissions.ROSTER_VIEW):
        return jsonify([]), 403
    
    if search_term:
        contacts = query.filter(Contact.Name.ilike(f'%{search_term}%')).all()
    else:
        contacts = query.all()
    
    # Batch populate users to avoid N+1 and fix invalid joinedload
    Contact.populate_users(contacts, club_id)

    # Build officer set from ContactClub
    officer_ids = set(
        cc.contact_id for cc in ContactClub.query.filter_by(club_id=club_id, is_officer=True).all()
    )

    contacts_data = [{
        "id": c.id,
        "Name": c.Name,
        "Type": c.Type,
        "Phone_Number": c.Phone_Number,
        "UserRole": c.user.primary_role_name if c.user else None,
        "is_officer": c.id in officer_ids,
        "Home_Club": c.home_club
    } for c in contacts]
    return jsonify(contacts_data)


@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    # Regular users only see Members; Staff and above see all.
    can_view_all = is_authorized(Permissions.ROSTER_VIEW)
    can_view_members = is_authorized(Permissions.ROSTER_VIEW)

    if not can_view_all:
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    from .utils import get_terms, get_active_term, get_date_ranges_for_terms
    terms = get_terms()
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    current_term = get_active_term(terms)
    
    if not start_date and not end_date:
        # Default to current term
        if current_term:
            start_date = current_term['start']
            end_date = current_term['end']
            
    # Flag to distinguish between "User didn't filter" (show all? or default?) 
    # and "User filtered but found nothing" (show nothing).
    should_filter = bool(start_date and end_date)


    


    club_id = get_current_club_id()
    
    # Optimization: Fetch counts only, let client fetch data async
    # Total contacts
    total_contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id).count()
    
    # Type counts
    type_counts_query = db.session.query(Contact.Type, func.count(Contact.id))\
        .join(ContactClub).filter(ContactClub.club_id == club_id)\
        .group_by(Contact.Type).all()
    type_counts = {t: c for t, c in type_counts_query}
    
    contacts = []
    contacts_json_data = []

    all_pathways = Pathway.query.filter_by(type='pathway', status='active').order_by(Pathway.name).all()
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    mentor_candidates = Contact.query.join(ContactClub).filter(
        ContactClub.club_id == club_id,
        Contact.Type.in_(['Member', 'Past Member'])
    ).order_by(Contact.Name.asc()).all()

    can_view_all_logs = is_authorized(Permissions.SPEECH_LOGS_MANAGE)


    return render_template('contacts.html',
                           contacts=contacts,
                           contacts_json_data=contacts_json_data,
                           pathways=pathways,
                           total_contacts=total_contacts,
                           type_counts=type_counts,
                           mentor_candidates=mentor_candidates,
                           can_view_all_logs=can_view_all_logs,
                           can_view_members=can_view_members,
                           can_send_messages=can_view_all,
                           terms=terms,
                           start_date=start_date,
                           end_date=end_date,
                           current_term=current_term)


@contacts_bp.route('/contacts/cards')
@login_required
def member_cards():
    """Renders the member cards view page."""
    can_view_all = is_authorized(Permissions.ROSTER_VIEW)
    can_view_members = is_authorized(Permissions.ROSTER_VIEW)

    if not can_view_all:
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    return render_template('member_cards.html',
                           can_view_members=can_view_members,
                           can_view_all=can_view_all)


@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    has_edit_permission = is_authorized(Permissions.ROSTER_EDIT) or (current_user.is_authenticated and contact_id and current_user.contact_id == contact_id)
    has_add_guest = not contact_id and is_authorized(Permissions.ROSTER_EDIT)
    
    if not (has_edit_permission or has_add_guest):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message="You don't have permission to perform this action."), 403
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.method == 'GET' and contact:
        # User-level Home Club selector (drives User.home_club). Only
        # relevant when contact is linked to a user. Reads from
        # UserClub.is_home, NOT from contact.home_club (those are
        # independent fields — see docs/CONTACT_USER_CLUB_MODEL.md).
        user_clubs_data = []
        home_club_id = None

        user = contact.user  # Uses current club context
        if user:
            ucs = UserClub.query.filter_by(user_id=user.id).options(joinedload(UserClub.club)).all()
            user_clubs_data = [{'id': uc.club.id, 'name': uc.club.club_name} for uc in ucs]
            home_uc = next((uc for uc in ucs if uc.is_home), None)
            if home_uc:
                home_club_id = home_uc.club_id

        # Check is_officer
        current_club_id = get_current_club_id()
        cc = ContactClub.query.filter_by(contact_id=contact.id, club_id=current_club_id).first()
        is_officer = cc.is_officer if cc else False

        # Get mentor candidates for the current club
        mentor_candidates = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == current_club_id,
            Contact.Type.in_(['Member', 'Past Member'])
        ).order_by(Contact.Name.asc()).all()
        mentor_candidates_data = [{'id': m.id, 'name': m.Name} for m in mentor_candidates]

        return jsonify({
            'contact': {
                'id': contact.id,
                'Name': contact.Name,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'Email': contact.Email,
                'Type': contact.Type,
                'is_officer': is_officer,
                'Phone_Number': contact.Phone_Number,
                'Bio': contact.Bio,
                'Member_ID': contact.Member_ID,
                'Completed_Paths': contact.Completed_Paths,
                'registered_paths': contact.get_member_pathways(),
                'DTM': contact.DTM,
                'current_path': contact.Current_Path,
                'next_project': contact.Next_Project,
                'credentials': contact.credentials,
                'Avatar_URL': contact.Avatar_URL,
                'mentor_id': contact.Mentor_ID,
                # Contact-level home club (the new field). Independent
                # from user_clubs/home_club_id above.
                'home_club': contact.home_club
            },
            'user_clubs': user_clubs_data,
            'home_club_id': home_club_id,
            'is_sysadmin': is_authorized(Permissions.SYSADMIN),
            'is_clubadmin': current_user.has_role(Permissions.CLUBADMIN),
            'current_club_id': get_current_club_id(),
            'mentor_candidates': mentor_candidates_data
        })


    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip() or None
        last_name = request.form.get('last_name', '').strip() or None
        name = request.form.get('name', '').strip()
        
        email = request.form.get('email', '').strip() or None
        contact_type = request.form.get('type', 'Guest')
        
        # Architectural Decision: All new contacts created via the contact form 
        # must be guests. Members are created via user registration or conversion.
        if not contact_id:
            contact_type = 'Guest'
            
        club = request.form.get('club', '').strip() or None
        phone = request.form.get('phone_number', '').strip() or None
        bio = request.form.get('bio', '').strip() or None
        member_id = request.form.get('member_id', '').strip() or None
        
        # Mentor Logic
        mentor_id_val = request.form.get('mentor_id')
        mentor_id = int(mentor_id_val) if mentor_id_val and int(mentor_id_val) != 0 else None

        if contact_id:
            # Update Existing Contact
            contact = Contact.query.get_or_404(contact_id)
            contact.first_name = first_name
            contact.last_name = last_name
            contact.Name = name
            contact.Email = email
            contact.Type = contact_type
            contact.Phone_Number = phone
            contact.Bio = bio
            contact.Member_ID = member_id
            contact.Mentor_ID = mentor_id

            # Contact-level home club (independent from User.home_club —
            # see docs/CONTACT_USER_CLUB_MODEL.md). Plain text input on
            # the form. Trim, treat empty as null.
            contact_home_club_val = request.form.get('contact_home_club', '').strip() or None
            contact.home_club = contact_home_club_val[:200] if contact_home_club_val else None

            # Manual overrides for completed paths and DTM if present in form
            if 'completed_paths' in request.form:
                new_completed = request.form.get('completed_paths')
                if contact.Completed_Paths != new_completed:
                    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify(success=False, message="You don't have permission to modify completed paths."), 403
                        flash("You don't have permission to modify completed paths.", 'error')
                        return redirect(url_for('contacts_bp.show_contacts'))
                    contact.Completed_Paths = new_completed
            contact.DTM = 'dtm' in request.form
            
            # Update is_officer flag if user is ClubAdmin
            if current_user.has_role(Permissions.CLUBADMIN) or is_authorized(Permissions.SYSADMIN):
                current_club_id = get_current_club_id()
                cc = ContactClub.query.filter_by(contact_id=contact.id, club_id=current_club_id).first()
                new_is_officer = 'is_officer' in request.form
                if cc:
                    cc.is_officer = new_is_officer
                elif new_is_officer:
                    cc = ContactClub(contact_id=contact.id, club_id=current_club_id, is_officer=True)
                    db.session.add(cc)
            
            # Auto-populate Name from parts if they exist
            # Force update using form data to ensure persistence
            name_parts = [p for p in [first_name, last_name] if p]
            if name_parts:
                contact.Name = " ".join(name_parts)
            else:
                contact.update_name_from_parts(overwrite=True)
            
            # Validate Name is not empty
            if not contact.Name:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message='Name or first/last name is required.'), 400
                flash('Name or first/last name is required.', 'error')
                return redirect(url_for('contacts_bp.show_contacts'))
            
            # Update profile fields (Member/Officer specific)
            if contact_type in ['Member', 'Officer']:
                contact.Current_Path = request.form.get('current_path')
            
            # Update Home Club (if applicable)
            home_club_val = request.form.get('home_club_id')
            # Only update if the field was present in the form submission
            if 'home_club_id' in request.form:
                 # Prefer user linked via current club context
                 user = contact.user
                 if not user and member_id:
                     # Fallback: Find user via Member ID if contact is a Guest
                     from .models import User
                     user = User.query.filter_by(member_no=member_id).first()
                 
                 if user:
                     new_home_club_id = int(home_club_val) if home_club_val and str(home_club_val).strip() else None
                     current_home_club = user.home_club
                     current_home_club_id = current_home_club.id if current_home_club else None

                     if new_home_club_id and new_home_club_id != current_home_club_id:
                         # Security Enforcement: Non-SysAdmins can only set/propose the CURRENT club.
                         current_cid = get_current_club_id()
                         if not is_authorized(Permissions.SYSADMIN) and new_home_club_id != current_cid:
                             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                 return jsonify(success=False, message='You can only set the home club to the current club.'), 403
                             flash('You can only set the home club to the current club.', 'error')
                             return redirect(url_for('contacts_bp.show_contacts', club_id=current_cid))

                         # Target club for logging/messaging
                         target_club = Club.query.get(new_home_club_id) if new_home_club_id else None
                         club_name = target_club.club_name if target_club else "None"

                         # If self-editing or SysAdmin? Immediate update.
                         if current_user.id == user.id or is_authorized(Permissions.SYSADMIN):
                             user.set_home_club(new_home_club_id)
                             if current_user.id != user.id:
                                 flash(f'Home club for {user.username} has been updated to {club_name}.', 'success')
                         else:
                             # Send Proposal Message instead of updating for Club Admins
                             from .models import Message
                             target_club = db.session.get(Club, new_home_club_id) if new_home_club_id else None
                             club_name = target_club.club_name if target_club else "None"
                             
                             proposal_msg = Message(
                                 sender_id=current_user.id,
                                 recipient_id=user.id,
                                 subject=f"Home Club Change Proposal: {club_name}",
                                 body=f"Administrator {current_user.display_name} has proposed to set **{club_name}** as your home club.\n\n[HOME_CLUB_PROPOSAL:{current_user.id}:{new_home_club_id or 0}]"
                             )
                             db.session.add(proposal_msg)
                             flash(f'A home club change proposal has been sent to {user.username} for approval.', 'info')
            
            # Handle Avatar Upload
            file = request.files.get('avatar')
            if file and file.filename != '':
                from .utils import process_avatar
                avatar_url = process_avatar(file, contact.id)
                if avatar_url:
                    contact.Avatar_URL = avatar_url
            
            db.session.commit()
            
            # Sync metadata (this will also aggregate paths if we just added/removed some manually)
            from .utils import sync_contact_metadata
            has_new_avatar = file and file.filename != '' and avatar_url
            sync_contact_metadata(contact.id, sync_avatar=bool(has_new_avatar))
            
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                flash('Contact updated successfully!', 'success')
            target_contact = contact
        else:
            # Create New Contact
            new_contact_home_club = (request.form.get('contact_home_club', '').strip() or None)
            if new_contact_home_club:
                new_contact_home_club = new_contact_home_club[:200]
            new_contact = Contact(
                first_name=first_name,
                last_name=last_name,
                Name=name,
                Email=email,
                Type=contact_type,
                Date_Created=date.today(),
                Phone_Number=phone,
                Bio=bio,
                Member_ID=member_id,
                Mentor_ID=mentor_id,
                DTM='dtm' in request.form,
                Current_Path=request.form.get('current_path') if contact_type in ['Member', 'Officer'] else None,
                home_club=new_contact_home_club
            )
            
            # Auto-populate Name from parts if they exist
            new_contact.update_name_from_parts(overwrite=True)
            
            # Validate Name is not empty
            if not new_contact.Name:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message='Name or first/last name is required.'), 400
                flash('Name or first/last name is required.', 'error')
                return redirect(url_for('contacts_bp.show_contacts'))
            
            # Check for existing name
            existing_name = Contact.query.filter_by(Name=new_contact.Name).first()
            if existing_name:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False, 
                        'message': f"A contact with the name '{new_contact.Name}' already exists.",
                        'duplicate_contact': {
                            'id': existing_name.id,
                            'name': existing_name.Name,
                            'email': existing_name.Email,
                            'phone': existing_name.Phone_Number
                        }
                    }), 400
                flash(f"A contact with the name '{new_contact.Name}' already exists.", 'error')
                return redirect(url_for('contacts_bp.show_contacts'))
                
            # Check for existing email if provided
            if email:
                existing_email = Contact.query.filter_by(Email=email).first()
                if existing_email:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({
                            'success': False, 
                            'message': f"A contact with the email '{email}' already exists.",
                            'duplicate_contact': {
                                'id': existing_email.id,
                                'name': existing_email.Name,
                                'email': existing_email.Email,
                                'phone': existing_email.Phone_Number
                            }
                        }), 400
                    flash(f"A contact with the email '{email}' already exists.", 'error')
                    return redirect(url_for('contacts_bp.show_contacts'))

            # Check for existing phone if provided
            if phone:
                existing_phone = Contact.query.filter_by(Phone_Number=phone).first()
                if existing_phone:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({
                            'success': False, 
                            'message': f"A contact with the phone '{phone}' already exists.",
                            'duplicate_contact': {
                                'id': existing_phone.id,
                                'name': existing_phone.Name,
                                'email': existing_phone.Email,
                                'phone': existing_phone.Phone_Number
                            }
                        }), 400
                    flash(f"A contact with the phone '{phone}' already exists.", 'error')
                    return redirect(url_for('contacts_bp.show_contacts'))
            
            db.session.add(new_contact)
            db.session.commit() # Commit to get ID for avatar naming
            
            # Handle Avatar Upload for new contact
            file = request.files.get('avatar')
            if file and file.filename != '':
                from .utils import process_avatar
                avatar_url = process_avatar(file, new_contact.id)
                if avatar_url:
                    new_contact.Avatar_URL = avatar_url
                    db.session.commit()

            # Associate with current club
            current_cid = get_current_club_id()
            if current_cid:
                is_officer = False
                if current_user.has_role(Permissions.CLUBADMIN) or is_authorized(Permissions.SYSADMIN):
                    is_officer = 'is_officer' in request.form
                db.session.add(ContactClub(
                    contact_id=new_contact.id,
                    club_id=current_cid,
                    is_officer=is_officer
                ))
                db.session.commit()

            # Sync metadata 
            from .utils import sync_contact_metadata
            sync_contact_metadata(new_contact.id)
            
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                flash('Contact added successfully!', 'success')
            target_contact = new_contact

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=True, contact={'id': target_contact.id, 'Name': target_contact.Name, 'Type': target_contact.Type})

        referer = request.form.get('referer') or request.args.get('referer')
        if referer:
            if 'roster' in referer:
                separator = '&' if '?' in referer else '?'
                encoded_name = urllib.parse.quote(target_contact.Name)
                redirect_url = f"{referer}{separator}new_contact_id={target_contact.id}&new_contact_name={encoded_name}&new_contact_type={target_contact.Type}"
                return redirect(redirect_url)
            else:
                return redirect(referer)
            
        return redirect(url_for('contacts_bp.show_contacts'))


    all_pathways = Pathway.query.filter_by(type='pathway', status='active').order_by(Pathway.name).all()
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)
    
    club_id = get_current_club_id()
    mentor_candidates = Contact.query.join(ContactClub).filter(
        ContactClub.club_id == club_id,
        Contact.Type.in_(['Member', 'Past Member'])
    ).order_by(Contact.Name.asc()).all()
    
    return render_template('contact_form.html', contact=contact, pathways=pathways, mentor_candidates=mentor_candidates)


@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
@authorized_club_required
@club_permission_required(Permissions.ROSTER_EDIT)
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if contact.Type != 'Guest':
        msg = "Only Guest contacts can be deleted directly. Members and Officers must be managed through their user accounts."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message=msg), 403
        flash(msg, 'error')
        return redirect(url_for('contacts_bp.show_contacts'))

    # Nullify references that don't have cascades
    
    # 1. Meeting awards and managers
    Meeting.query.filter(Meeting.best_table_topic_id == contact_id).update({"best_table_topic_id": None})
    Meeting.query.filter(Meeting.best_evaluator_id == contact_id).update({"best_evaluator_id": None})
    Meeting.query.filter(Meeting.best_speaker_id == contact_id).update({"best_speaker_id": None})
    Meeting.query.filter(Meeting.best_role_taker_id == contact_id).update({"best_role_taker_id": None})
    Meeting.query.filter(Meeting.manager_id == contact_id).update({"manager_id": None})
    
    # 2. UserClub mentors
    UserClub.query.filter(UserClub.mentor_id == contact_id).update({"mentor_id": None})
    
    # 3. Contact mentors (mentees of this contact)
    Contact.query.filter(Contact.Mentor_ID == contact_id).update({"Mentor_ID": None})
    
    # 4. SessionLogs (owners relationship) via OwnerMeetingRoles
    OwnerMeetingRoles.query.filter_by(contact_id=contact_id).delete(synchronize_session=False)

    # 5. Votes (contact_id)
    Vote.query.filter_by(contact_id=contact_id).update({"contact_id": None})

    # 6. ExComm (officer positions via association table)
    from .models.excomm_officer import ExcommOfficer
    ExcommOfficer.query.filter_by(contact_id=contact_id).delete(synchronize_session=False)

    db.session.delete(contact)
    db.session.commit()
    
    msg = 'Contact deleted successfully!'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, message=msg)
    
    flash(msg, 'success')
    return redirect(url_for('contacts_bp.show_contacts'))


@contacts_bp.route('/contacts/merge', methods=['POST'])
@login_required
@authorized_club_required
def merge_contacts_route():
    if not is_authorized(Permissions.ROSTER_EDIT):
        return jsonify(success=False, message="Permission denied"), 403
        
    data = request.get_json()
    contact_ids = data.get('contact_ids', [])
    
    if len(contact_ids) < 2:
        return jsonify(success=False, message="At least two contacts are required for merging."), 400
        
    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    if len(contacts) != len(contact_ids):
        return jsonify(success=False, message="One or more contacts not found."), 404
        
    # Primary Selection Logic: 
    # 1. If any contact is a Member (or non-Guest), the oldest one is primary.
    # 2. If all contacts are Guests, the oldest Guest is primary.
    
    def get_sort_key(c):
        # Type priority: 0 for anything non-Guest, 1 for Guest
        type_priority = 0 if c.Type != 'Guest' else 1
        # Older dates (smaller) should come first
        created_date = c.Date_Created or date.max
        return (type_priority, created_date, c.id)
        
    sorted_contacts = sorted(contacts, key=get_sort_key)
    primary = sorted_contacts[0]
    secondary_ids = [c.id for c in sorted_contacts[1:]]
    
    try:
        Contact.merge_contacts(primary.id, secondary_ids)
        return jsonify(success=True, message=f"Merged into {primary.Name}.", primary_id=primary.id)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error merging contacts: {str(e)}")
        return jsonify(success=False, message="An internal error occurred during merging."), 500


@contacts_bp.route('/api/contact', methods=['POST'])
@login_required
def create_contact_api():
    if not is_authorized(Permissions.ROSTER_EDIT):
        return jsonify({'error': 'Permission denied'}), 403

    try:
        data = request.get_json()

        if not data.get('name') or not data.get('type'):
            return jsonify({'error': 'Name and Type are required'}), 400

        existing_contact = Contact.query.filter_by(Name=data['name']).first()
        if existing_contact:
            return jsonify({'error': f"A contact with the name '{data['name']}' already exists."}), 400

        if data.get('email'):
            existing_email = Contact.query.filter_by(
                Email=data['email']).first()
            if existing_email:
                return jsonify({'error': f"A contact with the email '{data['email']}' already exists."}), 400

        if data.get('phone'):
            existing_phone = Contact.query.filter_by(
                Phone_Number=data['phone']).first()
            if existing_phone:
                return jsonify({'error': f"A contact with the phone '{data['phone']}' already exists."}), 400

        # Architectural Decision: All contacts created via the API must be guests.
        contact_type = 'Guest'

        new_contact = Contact(
            Name=data['name'],
            Email=data.get('email') or None,
            Type=contact_type,
            DTM=data.get('dtm', False),
            Date_Created=date.today(),
            Phone_Number=data.get('phone') or None
        )

        db.session.add(new_contact)
        db.session.commit()

        # Associate with current club
        current_cid = get_current_club_id()
        if current_cid:
            db.session.add(ContactClub(
                contact_id=new_contact.id,
                club_id=current_cid
            ))
            db.session.commit()

        return jsonify({
            'id': new_contact.id,
            'name': new_contact.Name,
            'type': new_contact.Type,
            'email': new_contact.Email,
            'phone': new_contact.Phone_Number
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@contacts_bp.route('/api/contacts/all')
@login_required
def get_all_contacts_api():
    """API endpoint to fetch all contacts for client-side caching."""
    can_view_all = is_authorized(Permissions.ROSTER_VIEW)
    can_view_members = is_authorized(Permissions.ROSTER_VIEW)

    if not can_view_all:
        return jsonify({'error': 'Permission denied'}), 403

    club_id = get_current_club_id()
    
    # --- DATE FILTER LOGIC ---
    from .utils import get_terms, get_active_term
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    date_ranges = []
    should_filter = False
    
    if start_date and end_date:
        should_filter = True
        date_ranges = [(start_date, end_date)]
        
    terms_list = request.args.getlist('term')
    if terms_list:
        should_filter = True
        all_terms = get_terms()
        term_map = {t['id']: t for t in all_terms}
        for term_id in terms_list:
            if term_id in term_map:
                date_ranges.append((term_map[term_id]['start'], term_map[term_id]['end']))
    
    from sqlalchemy import or_,  and_, false
    def apply_date_filter(query, date_column):
        if not date_ranges:
            if should_filter:
                 # User wanted to filter, but ranges are empty -> Match Nothing
                 return query.filter(false())
            else:
                 # No filter applied
                 return query
                 
        conditions = [date_column.between(start, end) for start, end in date_ranges]
        return query.filter(or_(*conditions))

    query = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)
    
    if not can_view_all:
        query = query.filter(Contact.Type == 'Member')
        
    contacts = query.options(joinedload(Contact.mentor),)\
        .order_by(Contact.Name.asc()).all()
    Contact.populate_users(contacts, club_id)
    
    # --- LIFETIME METRICS ---
    # 1. Lifetime Attendance (for Qualification)
    lifetime_attendance_counts = db.session.query(
        Roster.contact_id, func.count(Roster.id)
    ).join(Meeting, Roster.meeting_id == Meeting.id).filter(
        Roster.contact_id.isnot(None),
        Meeting.club_id == club_id
    ).group_by(Roster.contact_id).all()
    # lifetime_attendance_map = {c_id: count for c_id, count in lifetime_attendance_counts} # Not used for qual, but good to have?

    # 2. Lifetime Roles (for Qualification)
    lifetime_roles_query = db.session.query(
        OwnerMeetingRoles.contact_id, Meeting.Meeting_Number, OwnerMeetingRoles.role_id, MeetingRole.name
    ).join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
     .join(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
     .filter(
        MeetingRole.type.in_(['standard', 'club-specific']),
        Meeting.club_id == club_id
    )
    lifetime_distinct_roles = lifetime_roles_query.distinct().all()

    lifetime_tt_count = {}
    lifetime_other_role_count = {}

    for owner_id, _, _, role_name in lifetime_distinct_roles:
        r_name = role_name.strip() if role_name else ""
        if r_name == "Topics Speaker":
            lifetime_tt_count[owner_id] = lifetime_tt_count.get(owner_id, 0) + 1
        else:
            lifetime_other_role_count[owner_id] = lifetime_other_role_count.get(owner_id, 0) + 1

    # 3. Lifetime Awards (for Qualification)
    lifetime_best_tt_map = {}
    for field in ['best_speaker_id', 'best_evaluator_id', 'best_table_topic_id', 'best_role_taker_id']:
        q = db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(
            getattr(Meeting, field).isnot(None),
            Meeting.club_id == club_id
        )
        counts = q.group_by(getattr(Meeting, field)).all()
        if field == 'best_table_topic_id':
             for c_id, count in counts:
                lifetime_best_tt_map[c_id] = count

    # --- FILTERED METRICS ---
    # 1. Attendance
    roster_query = db.session.query(
        Roster.contact_id, func.count(Roster.id)
    ).join(Meeting, Roster.meeting_id == Meeting.id).filter(
        Roster.contact_id.isnot(None),
        Meeting.club_id == club_id
    )
    roster_query = apply_date_filter(roster_query, Meeting.Meeting_Date)
    attendance_counts = roster_query.group_by(Roster.contact_id).all()
    attendance_map = {c_id: count for c_id, count in attendance_counts}

    # 2. Roles
    roles_query = db.session.query(
        OwnerMeetingRoles.contact_id, Meeting.Meeting_Number, OwnerMeetingRoles.role_id, MeetingRole.name
    ).join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
     .join(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
     .filter(
        MeetingRole.type.in_(['standard', 'club-specific']),
        Meeting.club_id == club_id
    )
    roles_query = apply_date_filter(roles_query, Meeting.Meeting_Date)
    distinct_roles = roles_query.distinct().all()

    role_map = {}
    contact_tt_count = {}

    for owner_id, _, _, role_name in distinct_roles:
        r_name = role_name.strip() if role_name else ""
        if r_name == "Topics Speaker":
            contact_tt_count[owner_id] = contact_tt_count.get(owner_id, 0) + 1
        else:
            role_map[owner_id] = role_map.get(owner_id, 0) + 1

    # 3. Awards
    award_map = {}

    for field in ['best_speaker_id', 'best_evaluator_id', 'best_table_topic_id', 'best_role_taker_id']:
        q = db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(
            getattr(Meeting, field).isnot(None),
            Meeting.club_id == club_id
        )
        q = apply_date_filter(q, Meeting.Meeting_Date)
        counts = q.group_by(getattr(Meeting, field)).all()
        for c_id, count in counts:
            award_map[c_id] = award_map.get(c_id, 0) + count

    def check_membership_qualification(contact_type, tt_count, best_tt_count, other_role_count):
        if contact_type != 'Guest':
            return False
        return (tt_count >= 4 and best_tt_count >= 1 and other_role_count >= 2)

    # Batch populate primary clubs to avoid N+1 queries in the loop below
    Contact.populate_primary_clubs(contacts)

    # Build officer IDs set from ContactClub
    officer_ids = set(
        cc.contact_id for cc in ContactClub.query.filter_by(club_id=club_id, is_officer=True).all()
    )

    # Build officer title map: contact_id -> MeetingRole.name from the
    # current/most-recent ExComm for this club. Used by the contacts list
    # to surface the officer's actual title (President, VPE, ...) instead
    # of a generic badge.
    from datetime import date as _date
    from .models.excomm import ExComm
    from .models.excomm_officer import ExcommOfficer
    current_excomm = (
        ExComm.query
        .filter(ExComm.club_id == club_id)
        .filter((ExComm.start_date.is_(None)) | (ExComm.start_date <= _date.today()))
        .filter((ExComm.end_date.is_(None)) | (ExComm.end_date >= _date.today()))
        .order_by(ExComm.start_date.desc())
        .first()
    )
    officer_title_map = {}
    if current_excomm:
        for officer_link in current_excomm.officers:
            if officer_link.meeting_role and officer_link.meeting_role.name:
                officer_title_map[officer_link.contact_id] = officer_link.meeting_role.name

    # Build JSON response
    contacts_data = []
    for c in contacts:
        # Filtered metrics
        tt = contact_tt_count.get(c.id, 0)
        att = attendance_map.get(c.id, 0)
        award = award_map.get(c.id, 0)
        roles = role_map.get(c.id, 0)
        
        # Lifetime metrics for qualification
        l_tt = lifetime_tt_count.get(c.id, 0)
        l_best_tt = lifetime_best_tt_map.get(c.id, 0)
        l_other = lifetime_other_role_count.get(c.id, 0)
        
        primary_club = c.get_primary_club()
        
        contacts_data.append({
            'id': c.id,
            'Name': c.Name,
            'Type': c.Type,
            'Phone_Number': c.Phone_Number if c.Phone_Number else '-',
            'Club': primary_club.club_name if primary_club else '-',
            'Home_Club': c.home_club if c.home_club else '-',
            'Completed_Paths': c.Completed_Paths if c.Completed_Paths else '-',
            'credentials': c.credentials if c.credentials else '-',
            'Next_Project': c.Next_Project if c.Next_Project else '-',
            'Mentor': c.mentor.Name if c.mentor else '-',
            'Member_ID': c.Member_ID,
            'DTM': c.DTM,
            'Avatar_URL': c.Avatar_URL,
            'role_count': roles,
            'tt_count': tt,
            'attendance_count': att,
            'award_count': award,
            'is_qualified': check_membership_qualification(c.Type, l_tt, l_best_tt, l_other),
            'has_user': c.user is not None,
            'user_id': c.user.id if c.user else None,
            'user_role': c.user.primary_role_name if c.user else None,
            'is_officer': c.id in officer_ids,
            'officer_title': officer_title_map.get(c.id),
            'is_connected': c.is_connected,
            'Email': c.Email if c.Email else '-',
            'first_name': c.first_name if c.first_name else '-',
            'last_name': c.last_name if c.last_name else '-',
            'username': c.user.username if c.user else '-',
            'Date_Created': c.Date_Created.strftime('%Y-%m-%d') if c.Date_Created else '-'
        })

    return jsonify(contacts_data)


@contacts_bp.route('/contact/toggle_connection/<int:contact_id>', methods=['POST'])
@login_required
def toggle_contact_connection(contact_id):
    if not is_authorized(Permissions.ROSTER_EDIT):
        return jsonify(success=False, message="Permission denied"), 403
    
    contact = Contact.query.get_or_404(contact_id)
    contact.is_connected = not contact.is_connected
    db.session.commit()
    
    return jsonify(success=True, is_connected=contact.is_connected)
