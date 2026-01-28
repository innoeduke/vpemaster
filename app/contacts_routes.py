# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from . import db
from .models import Contact, SessionLog, Pathway, ContactClub, Meeting, Vote, ExComm, UserClub, Roster, SessionType, MeetingRole, OwnerMeetingRoles
from .auth.utils import login_required, is_authorized
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
    
    if search_term:
        contacts = query.filter(Contact.Name.ilike(f'%{search_term}%')).all()
    else:
        contacts = query.all()
    
    # Batch populate users to avoid N+1 and fix invalid joinedload
    Contact.populate_users(contacts, club_id)

    contacts_data = [{
        "id": c.id,
        "Name": c.Name,
        "Type": c.Type,
        "Phone_Number": c.Phone_Number,
        "UserRole": c.user.primary_role_name if c.user else None,
        "is_officer": c.user.has_role(Permissions.STAFF) if c.user else False
    } for c in contacts]
    return jsonify(contacts_data)


@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    if not is_authorized(Permissions.CONTACT_BOOK_VIEW):
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    from .utils import get_terms, get_active_term, get_date_ranges_for_terms
    terms = get_terms()
    
    # Multi-select support
    selected_term_ids = request.args.getlist('term')
    
    current_term = get_active_term(terms)
    
    if not selected_term_ids:
        # Default to current term
        if current_term:
            selected_term_ids = [current_term['id']]
        elif terms:
            selected_term_ids = [terms[0]['id']]
            
    date_ranges = get_date_ranges_for_terms(selected_term_ids, terms)
    
    # Flag to distinguish between "User didn't filter" (show all? or default?) 
    # and "User filtered but found nothing" (show nothing).
    should_filter = bool(selected_term_ids)


    


    club_id = get_current_club_id()
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
        .options(joinedload(Contact.mentor))\
        .order_by(Contact.Name.asc()).all()
    Contact.populate_users(contacts, club_id)
    # Batch populate primary clubs to avoid N+1 queries in template
    Contact.populate_primary_clubs(contacts)
    
    # Helper to build date filter
    from sqlalchemy import or_,  and_, false
    def apply_date_filter(query, date_column):
        if not date_ranges:
            if should_filter:
                 # User wanted to filter, but ranges are empty -> Match Nothing
                 return query.filter(false())
            else:
                 # No filter applied (shouldn't happen with current default logic, but safe fallback)
                 return query
                 
        conditions = [date_column.between(start, end) for start, end in date_ranges]
        return query.filter(or_(*conditions))

    # 1. Attendance (Roster)
    # Count how many times each contact appears in Roster
    
    roster_query = db.session.query(
        Roster.contact_id, func.count(Roster.id)
    ).join(Meeting, Roster.meeting_number == Meeting.Meeting_Number).filter(
        Roster.contact_id.isnot(None),
        Meeting.club_id == club_id
    )
    
    roster_query = apply_date_filter(roster_query, Meeting.Meeting_Date)
    attendance_counts = roster_query.group_by(Roster.contact_id).all()
    attendance_map = {c_id: count for c_id, count in attendance_counts}

    # 2. Roles (SessionLog where SessionType is a Role)
    # We want to count distinct (Meeting, Role) pairs per user.
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
    
    # Track granular counts for "Star Guest" logic
    # Criteria: 4+ Topics Speaker, 1+ Best Table Topic, 2+ Other Roles
    contact_tt_count = {}
    contact_other_role_count = {}

    for owner_id, _, _, role_name in distinct_roles:
        role_map[owner_id] = role_map.get(owner_id, 0) + 1
        
        r_name = role_name.strip() if role_name else ""
        if r_name == "Topics Speaker":
            contact_tt_count[owner_id] = contact_tt_count.get(owner_id, 0) + 1
        else:
            contact_other_role_count[owner_id] = contact_other_role_count.get(owner_id, 0) + 1

    # 3. Awards (Meeting Best X)
    
    # helper to get counts for a specific field
    def get_award_counts(field):
        q = db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(
            getattr(Meeting, field).isnot(None),
            Meeting.club_id == club_id
        )
        q = apply_date_filter(q, Meeting.Meeting_Date)
        return q.group_by(getattr(Meeting, field)).all()

    award_map = {}
    best_tt_map = {} # Track Best Table Topic separately

    for field in ['best_speaker_id', 'best_evaluator_id', 'best_table_topic_id', 'best_role_taker_id']:
        counts = get_award_counts(field)
        for c_id, count in counts:
            award_map[c_id] = award_map.get(c_id, 0) + count
            if field == 'best_table_topic_id':
                best_tt_map[c_id] = count

    def check_membership_qualification(tt_count, best_tt_count, other_role_count):
        """
        Determines if a guest meets the membership criteria:
        - 4+ Table Topic Speaker roles
        - 1+ Best Table Topic award
        - 2+ Other roles
        """
        return (tt_count >= 4 and best_tt_count >= 1 and other_role_count >= 2)

    # Attach to contacts
    for c in contacts:
        c.attendance_count = attendance_map.get(c.id, 0)
        c.role_count = role_map.get(c.id, 0)
        c.award_count = award_map.get(c.id, 0)
        
        # Calculate Qualification Status
        tt = contact_tt_count.get(c.id, 0)
        best_tt = best_tt_map.get(c.id, 0)
        other_roles = contact_other_role_count.get(c.id, 0)
        
        c.tt_count = tt  # Expose for frontend display
        c.is_qualified = check_membership_qualification(tt, best_tt, other_roles)

    # Sort contacts by role_count desc by default
    contacts.sort(key=lambda c: (c.role_count, c.is_qualified, c.tt_count), reverse=True)

    total_contacts = len(contacts)
    type_counts = {}
    for c in contacts:
        type_counts[c.Type] = type_counts.get(c.Type, 0) + 1
    
    # Sort types: Member first, then others
    sorted_types = sorted(type_counts.keys(), key=lambda x: (x not in ['Member'], x))
    
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

    can_view_all_logs = is_authorized(Permissions.SPEECH_LOGS_VIEW_ALL)

    # Prepare JSON data for client-side JS to avoid double-fetch and use correct filters
    contacts_json_data = []
    for c in contacts:
        # Use attached attributes if available (populated above), else defaults
        role_c = getattr(c, 'role_count', 0)
        tt_c = getattr(c, 'tt_count', 0)
        att_c = getattr(c, 'attendance_count', 0)
        award_c = getattr(c, 'award_count', 0)
        is_qual = getattr(c, 'is_qualified', False)
        
        primary_club = c.get_primary_club()
        
        contacts_json_data.append({
            'id': c.id,
            'Name': c.Name,
            'Type': c.Type,
            'Phone_Number': c.Phone_Number if c.Phone_Number else '-',
            'Club': primary_club.club_name if primary_club else '-',
            'Completed_Paths': c.Completed_Paths if c.Completed_Paths else '-',
            'credentials': c.credentials if c.credentials else '-',
            'Next_Project': c.Next_Project if c.Next_Project else '-',
            'Mentor': c.mentor.Name if c.mentor else '-',
            'Member_ID': c.Member_ID,
            'DTM': c.DTM,
            'Avatar_URL': c.Avatar_URL,
            'role_count': role_c,
            'tt_count': tt_c,
            'attendance_count': att_c,
            'award_count': award_c,
            'is_qualified': is_qual,
            'has_user': c.user is not None,
            # 'user_role': ... (Not strictly needed for the table display, can add if needed)
            # 'is_officer': ...
        })

    return render_template('contacts.html', 
                           contacts=contacts,
                           contacts_json_data=contacts_json_data,
                           pathways=pathways,
                           total_contacts=total_contacts, 
                           type_counts=type_counts,
                           contact_types=sorted_types,
                           mentor_candidates=mentor_candidates,
                           can_view_all_logs=can_view_all_logs,
                           terms=terms,
                           selected_term_ids=selected_term_ids,
                           current_term=current_term)


@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    if not is_authorized(Permissions.CONTACT_BOOK_EDIT):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message="You don't have permission to perform this action."), 403
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.method == 'GET' and contact:
        # Fetch User Clubs for Home Club Selector
        user_clubs_data = []
        home_club_id = None
        
        # Check if contact is linked to a user
        # Note: We need to check across ALL clubs, so we look for any UserClub with this contact_id or user_id
        # Actually, contact.user property checks current club context.
        # But for Home Club, we might want to see ALL clubs the user is in.
        
        # Strategy: Find the User associated with this contact.
        # Since contact <-> user is many-to-many via UserClub, a contact might be associated with a user in THIS club.
        # If so, get that user's other clubs.
        
        user = contact.user # Uses current club context
        if user:
            ucs = UserClub.query.filter_by(user_id=user.id).options(joinedload(UserClub.club)).all()
            user_clubs_data = [{'id': uc.club.id, 'name': uc.club.club_name} for uc in ucs]
            
            home_uc = next((uc for uc in ucs if uc.is_home), None)
            home_club_id = home_uc.club_id if home_uc else None

        return jsonify({
            'contact': {
                'id': contact.id,
                'Name': contact.Name,
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'Email': contact.Email,
                'Type': contact.Type,
                'Phone_Number': contact.Phone_Number,
                'Bio': contact.Bio,
                'Member_ID': contact.Member_ID,
                'Completed_Paths': contact.Completed_Paths,
                'DTM': contact.DTM,
                'current_path': contact.Current_Path,
                'next_project': contact.Next_Project,
                'credentials': contact.credentials,
                'Avatar_URL': contact.Avatar_URL,
                'mentor_id': contact.Mentor_ID
            },
            'user_clubs': user_clubs_data,
            'home_club_id': home_club_id
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
            
            # Manual overrides for completed paths and DTM if present in form
            if 'completed_paths' in request.form:
                contact.Completed_Paths = request.form.get('completed_paths')
            if 'dtm' in request.form:
                contact.DTM = 'dtm' in request.form
            
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
                 user = contact.user
                 if user:
                     new_home_club_id = int(home_club_val) if home_club_val else None
                     user.set_home_club(new_home_club_id)
            
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
            sync_contact_metadata(contact.id)
            
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                flash('Contact updated successfully!', 'success')
            target_contact = contact
        else:
            # Create New Contact
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
                Current_Path=request.form.get('current_path') if contact_type in ['Member', 'Officer'] else None
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
                db.session.add(ContactClub(
                    contact_id=new_contact.id,
                    club_id=current_cid
                ))
                db.session.commit()

            # Sync metadata 
            from .utils import sync_contact_metadata
            sync_contact_metadata(new_contact.id)
            
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                flash('Contact added successfully!', 'success')
            target_contact = new_contact

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=True, contact={'id': target_contact.id, 'Name': target_contact.Name})

        referer = request.form.get('referer') or request.args.get('referer')
        if referer and 'roster' in referer:
            separator = '&' if '?' in referer else '?'
            redirect_url = f"{referer}{separator}new_contact_id={target_contact.id}&new_contact_name={target_contact.Name}&new_contact_type={target_contact.Type}"
            return redirect(redirect_url)
            
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
def delete_contact(contact_id):
    contact = Contact.query.get_or_404(contact_id)
    if contact.Type != 'Guest':
        flash("Only Guest contacts can be deleted directly. Members and Officers must be managed through their user accounts.", 'error')
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
    
    # 4. SessionLogs (owners relationship)
    # Replaced with OwnerMeetingRoles cleanup
    OwnerMeetingRoles.query.filter_by(contact_id=contact_id).delete(synchronize_session=False)

    # 5. Votes (contact_id)
    Vote.query.filter_by(contact_id=contact_id).update({"contact_id": None})

    # 6. ExComm (officer positions)
    ExComm.query.filter(ExComm.president_id == contact_id).update({"president_id": None})
    ExComm.query.filter(ExComm.vpe_id == contact_id).update({"vpe_id": None})
    ExComm.query.filter(ExComm.vpm_id == contact_id).update({"vpm_id": None})
    ExComm.query.filter(ExComm.vppr_id == contact_id).update({"vppr_id": None})
    ExComm.query.filter(ExComm.secretary_id == contact_id).update({"secretary_id": None})
    ExComm.query.filter(ExComm.treasurer_id == contact_id).update({"treasurer_id": None})
    ExComm.query.filter(ExComm.saa_id == contact_id).update({"saa_id": None})
    ExComm.query.filter(ExComm.ipp_id == contact_id).update({"ipp_id": None})
    
    db.session.delete(contact)
    db.session.commit()
    flash('Contact deleted successfully!', 'success')
    return redirect(url_for('contacts_bp.show_contacts'))


@contacts_bp.route('/api/contact', methods=['POST'])
@login_required
def create_contact_api():
    if not is_authorized(Permissions.CONTACT_BOOK_EDIT):
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
    if not is_authorized(Permissions.CONTACT_BOOK_VIEW):
        return jsonify({'error': 'Permission denied'}), 403

    
    club_id = get_current_club_id()
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
        .options(joinedload(Contact.mentor),)\
        .order_by(Contact.Name.asc()).all()
    Contact.populate_users(contacts, club_id)
    
    # Calculate participation metrics (same logic as show_contacts)
    six_months_ago = date.today() - timedelta(days=180)
    # 1. Attendance counts
    attendance_counts = db.session.query(
        Roster.contact_id, func.count(Roster.id)
    ).join(Meeting, Roster.meeting_number == Meeting.Meeting_Number).filter(
        Roster.contact_id.isnot(None),
        Meeting.club_id == club_id,
        Meeting.Meeting_Date >= six_months_ago
    ).group_by(Roster.contact_id).all()
    attendance_map = {c_id: count for c_id, count in attendance_counts}

    # 2. Role counts
    distinct_roles = db.session.query(
        OwnerMeetingRoles.contact_id, Meeting.Meeting_Number, OwnerMeetingRoles.role_id, MeetingRole.name
    ).join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
     .join(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
     .filter(
        MeetingRole.type.in_(['standard', 'club-specific']),
        Meeting.club_id == club_id,
        Meeting.Meeting_Date >= six_months_ago
    ).distinct().all()

    role_map = {}
    contact_tt_count = {}
    contact_other_role_count = {}

    for owner_id, _, _, role_name in distinct_roles:
        role_map[owner_id] = role_map.get(owner_id, 0) + 1
        r_name = role_name.strip() if role_name else ""
        if r_name == "Topics Speaker":
            contact_tt_count[owner_id] = contact_tt_count.get(owner_id, 0) + 1
        else:
            contact_other_role_count[owner_id] = contact_other_role_count.get(owner_id, 0) + 1

    # 3. Awards
    award_map = {}
    best_tt_map = {}

    for field in ['best_speaker_id', 'best_evaluator_id', 'best_table_topic_id', 'best_role_taker_id']:
        counts = db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(
            getattr(Meeting, field).isnot(None),
            Meeting.club_id == club_id,
            Meeting.Meeting_Date >= six_months_ago
        ).group_by(getattr(Meeting, field)).all()
        for c_id, count in counts:
            award_map[c_id] = award_map.get(c_id, 0) + count
            if field == 'best_table_topic_id':
                best_tt_map[c_id] = count

    def check_membership_qualification(tt_count, best_tt_count, other_role_count):
        return (tt_count >= 4 and best_tt_count >= 1 and other_role_count >= 2)

    # Batch populate primary clubs to avoid N+1 queries in the loop below
    Contact.populate_primary_clubs(contacts)

    # Build JSON response
    contacts_data = []
    for c in contacts:
        tt = contact_tt_count.get(c.id, 0)
        best_tt = best_tt_map.get(c.id, 0)
        other_roles = contact_other_role_count.get(c.id, 0)
        
        primary_club = c.get_primary_club()
        
        contacts_data.append({
            'id': c.id,
            'Name': c.Name,
            'Type': c.Type,
            'Phone_Number': c.Phone_Number if c.Phone_Number else '-',
            'Club': primary_club.club_name if primary_club else '-',
            'Completed_Paths': c.Completed_Paths if c.Completed_Paths else '-',
            'credentials': c.credentials if c.credentials else '-',
            'Next_Project': c.Next_Project if c.Next_Project else '-',
            'Mentor': c.mentor.Name if c.mentor else '-',
            'Member_ID': c.Member_ID,
            'DTM': c.DTM,
            'Avatar_URL': c.Avatar_URL,
            'role_count': role_map.get(c.id, 0),
            'tt_count': tt,
            'attendance_count': attendance_map.get(c.id, 0),
            'award_count': award_map.get(c.id, 0),
            'is_qualified': check_membership_qualification(tt, best_tt, other_roles),
            'has_user': c.user is not None,
            'user_role': c.user.primary_role_name if c.user else None,
            'is_officer': c.user.has_role(Permissions.STAFF) if c.user else False
        })

    return jsonify(contacts_data)
