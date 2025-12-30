# vpemaster/contacts_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from . import db
from .models import Contact, SessionLog, Pathway
from .auth.utils import login_required, is_authorized
from flask_login import current_user

from datetime import date

contacts_bp = Blueprint('contacts_bp', __name__)


@contacts_bp.route('/contacts/search')
@login_required
def search_contacts_by_name():
    search_term = request.args.get('q', '')
    if search_term:
        contacts = Contact.query.filter(
            Contact.Name.ilike(f'%{search_term}%')).all()
    else:
        contacts = Contact.query.all()

    contacts_data = [{
        "id": c.id,
        "Name": c.Name,
        "Type": c.Type,
        "UserRole": c.user.Role if c.user else None,
        "is_officer": c.user.is_officer if c.user else False
    } for c in contacts]
    return jsonify(contacts_data)


@contacts_bp.route('/contacts')
@login_required
def show_contacts():
    if not is_authorized('CONTACT_BOOK_VIEW'):
        flash("You don't have permission to view this page.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    from sqlalchemy.orm import joinedload
    contacts = Contact.query.options(joinedload(Contact.mentor)).outerjoin(
        Contact.user).order_by(Contact.Name.asc()).all()
    
    # 1. Attendance (Roster)
    # Count how many times each contact appears in Roster
    from .models import Roster, SessionType, Role
    from sqlalchemy import func
    
    attendance_counts = db.session.query(
        Roster.contact_id, func.count(Roster.id)
    ).filter(Roster.contact_id.isnot(None)).group_by(Roster.contact_id).all()
    attendance_map = {c_id: count for c_id, count in attendance_counts}

    # 2. Roles (SessionLog where SessionType is a Role)
    # We want to count distinct (Meeting, Role) pairs per user.
    distinct_roles = db.session.query(
        SessionLog.Owner_ID, SessionLog.Meeting_Number, SessionType.role_id, Role.name
    ).select_from(SessionLog).join(SessionType).join(Role).filter(
        SessionLog.Owner_ID.isnot(None),
        SessionType.role_id.isnot(None),
        Role.type.in_(['standard', 'club-specific'])
    ).distinct().all()

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
    from .models import Meeting
    
    # helper to get counts for a specific field
    def get_award_counts(field):
        return db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(getattr(Meeting, field).isnot(None)).group_by(getattr(Meeting, field)).all()

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

    mentor_candidates = Contact.query.filter(
        Contact.Type.in_(['Member', 'Past Member'])
    ).order_by(Contact.Name.asc()).all()

    return render_template('contacts.html', 
                           contacts=contacts, 
                           pathways=pathways,
                           total_contacts=total_contacts, 
                           type_counts=type_counts,
                           contact_types=sorted_types,
                           mentor_candidates=mentor_candidates)


@contacts_bp.route('/contact/form', methods=['GET', 'POST'])
@contacts_bp.route('/contact/form/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def contact_form(contact_id=None):
    if not is_authorized('CONTACT_BOOK_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    contact = None
    if contact_id:
        contact = Contact.query.get_or_404(contact_id)

    if request.method == 'GET' and contact:
        return jsonify({
            'contact': {
                'id': contact.id,
                'Name': contact.Name,
                'Email': contact.Email,
                'Type': contact.Type,
                'Club': contact.Club,
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
            }
        })

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name is required.', 'error')
            return redirect(url_for('contacts_bp.show_contacts'))

        email = request.form.get('email', '').strip() or None
        contact_type = request.form.get('type', 'Guest')
        club = request.form.get('club', '').strip() or 'SHLTMC'
        phone = request.form.get('phone_number', '').strip() or None
        bio = request.form.get('bio', '').strip() or None
        member_id = request.form.get('member_id', '').strip() or None
        
        # Mentor Logic
        mentor_id_val = request.form.get('mentor_id')
        mentor_id = int(mentor_id_val) if mentor_id_val and int(mentor_id_val) != 0 else None

        if contact_id:
            # Update Existing Contact
            contact = Contact.query.get_or_404(contact_id)
            contact.Name = name
            contact.Email = email
            contact.Type = contact_type
            contact.Club = club
            contact.Phone_Number = phone
            contact.Bio = bio
            contact.Member_ID = member_id
            contact.Mentor_ID = mentor_id
            
            # Update profile fields (Member/Officer specific)
            if contact_type in ['Member', 'Officer']:
                contact.Current_Path = request.form.get('current_path')
            
            # Handle Avatar Upload
            file = request.files.get('avatar')
            if file and file.filename != '':
                from .utils import process_avatar
                avatar_url = process_avatar(file, contact.id)
                if avatar_url:
                    contact.Avatar_URL = avatar_url
            
            db.session.commit()
            flash('Contact updated successfully!', 'success')
            target_contact = contact
        else:
            # Create New Contact
            # Check for existing name
            existing_name = Contact.query.filter_by(Name=name).first()
            if existing_name:
                flash(f"A contact with the name '{name}' already exists.", 'error')
                return redirect(url_for('contacts_bp.show_contacts'))
                
            # Check for existing email if provided
            if email:
                existing_email = Contact.query.filter_by(Email=email).first()
                if existing_email:
                    flash(f"A contact with the email '{email}' already exists.", 'error')
                    return redirect(url_for('contacts_bp.show_contacts'))

            new_contact = Contact(
                Name=name,
                Email=email,
                Type=contact_type,
                Club=club or 'SHLTMC',
                Date_Created=date.today(),
                Phone_Number=phone,
                Bio=bio,
                Member_ID=member_id,
                Mentor_ID=mentor_id,
                Current_Path=request.form.get('current_path') if contact_type in ['Member', 'Officer'] else None
            )
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

            # Sync metadata 
            from .utils import sync_contact_metadata
            sync_contact_metadata(new_contact.id)
            
            flash('Contact added successfully!', 'success')
            target_contact = new_contact

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=True, contact={'id': target_contact.id, 'Name': target_contact.Name})

        referer = request.args.get('referer')
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
    return render_template('contact_form.html', contact=contact, pathways=pathways)


@contacts_bp.route('/contact/delete/<int:contact_id>', methods=['POST'])
@login_required
def delete_contact(contact_id):
    if not is_authorized('CONTACT_BOOK_EDIT'):
        flash("You don't have permission to perform this action.", 'error')
        return redirect(url_for('agenda_bp.agenda'))

    SessionLog.query.filter_by(Owner_ID=contact_id).update({"Owner_ID": None})
    contact = Contact.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    return redirect(url_for('contacts_bp.show_contacts'))


@contacts_bp.route('/api/contact', methods=['POST'])
@login_required
def create_contact_api():
    if not is_authorized('CONTACT_BOOK_EDIT'):
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

        new_contact = Contact(
            Name=data['name'],
            Email=data.get('email') or None,
            Type=data['type'],
            Club=data.get('club') or 'SHLTMC',
            Date_Created=date.today(),
            Phone_Number=data.get('phone') or None
        )

        db.session.add(new_contact)
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
