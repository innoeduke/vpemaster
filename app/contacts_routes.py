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

    contacts = Contact.query.outerjoin(
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
    # If a user has multiple slots for the same role in the same meeting, it counts as 1.
    distinct_roles = db.session.query(
        SessionLog.Owner_ID, SessionLog.Meeting_Number, SessionType.role_id
    ).join(SessionType).join(Role).filter(
        SessionLog.Owner_ID.isnot(None),
        SessionType.role_id.isnot(None),
        Role.type.in_(['standard', 'club-specific'])
    ).distinct().all()

    role_map = {}
    for owner_id, _, _ in distinct_roles:
        role_map[owner_id] = role_map.get(owner_id, 0) + 1

    # 3. Awards (Meeting Best X)
    # We need to sum up best_speaker, best_evaluator, best_table_topic, best_role_taker
    # This is a bit manual
    from .models import Meeting
    
    # helper to get counts for a specific field
    def get_award_counts(field):
        return db.session.query(
            getattr(Meeting, field), func.count(Meeting.id)
        ).filter(getattr(Meeting, field).isnot(None)).group_by(getattr(Meeting, field)).all()

    award_map = {}
    for field in ['best_speaker_id', 'best_evaluator_id', 'best_table_topic_id', 'best_role_taker_id']:
        counts = get_award_counts(field)
        for c_id, count in counts:
            award_map[c_id] = award_map.get(c_id, 0) + count

    # Attach to contacts
    for c in contacts:
        c.attendance_count = attendance_map.get(c.id, 0)
        c.role_count = role_map.get(c.id, 0)
        c.award_count = award_map.get(c.id, 0)

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
        contact_data = {
            "id": contact.id,
            "Name": contact.Name,
            "Email": contact.Email or None,
            "Type": contact.Type,
            "Club": contact.Club,
            "Completed_Paths": contact.Completed_Paths,
            "DTM": contact.DTM,
            "Phone_Number": contact.Phone_Number,
            "Bio": contact.Bio,
            "credentials": contact.credentials,
            "current_path": contact.Current_Path,
            "next_project": contact.Next_Project,
            "mentor_id": contact.Mentor_ID,
            "has_user": True if contact.user else False
        }
        return jsonify(contact=contact_data)

    if request.method == 'POST':
        contact_name = request.form.get('name')
        email = request.form.get('email') or None

        if contact:
            # Logic for updating an existing contact
            contact.Name = contact_name
            contact.Email = email
            contact.Club = request.form.get('club')
            contact.Type = request.form.get('type')
            contact.Phone_Number = request.form.get('phone_number')
            contact.Bio = request.form.get('bio')
            
            # Update profile fields (Member/Officer specific)
            if request.form.get('type') in ['Member', 'Officer']:
                contact.Current_Path = request.form.get('current_path')
                
                mentor_id = request.form.get('mentor_id', 0, type=int)
                contact.Mentor_ID = mentor_id if mentor_id and mentor_id != 0 else None

            db.session.commit()
            
            # Sync metadata based on achievements
            from .utils import sync_contact_metadata
            sync_contact_metadata(contact.id)
        else:
            # Logic for creating a new contact
            existing_contact = Contact.query.filter_by(
                Name=contact_name).first()
            if existing_contact:
                message = f"A contact with the name '{contact_name}' already exists."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(success=False, message=message)
                else:
                    flash(message, 'error')
                    return redirect(url_for('contacts_bp.show_contacts'))

            if email:
                existing_email = Contact.query.filter_by(Email=email).first()
                if existing_email:
                    message = f"A contact with the email '{email}' already exists."
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify(success=False, message=message)
                    else:
                        flash(message, 'error')
                        return redirect(url_for('contacts_bp.show_contacts'))

            new_contact = Contact(
                Name=contact_name,
                Email=email,
                Club=request.form.get('club'),
                Date_Created=date.today(),
                Phone_Number=request.form.get('phone_number'),
                Bio=request.form.get('bio'),
                Current_Path=request.form.get('current_path'),
                Next_Project=request.form.get('next_project'),
                Mentor_ID=request.form.get('mentor_id', None, type=int) or None
            )
            db.session.add(new_contact)
            db.session.commit()

            # Sync metadata based on achievements
            from .utils import sync_contact_metadata
            sync_contact_metadata(new_contact.id)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=True, contact={'id': new_contact.id, 'Name': new_contact.Name, 'Phone_Number': new_contact.Phone_Number, 'Bio': new_contact.Bio})

        referer = request.args.get('referer')
        if referer and 'roster' in referer:
            separator = '&' if '?' in referer else '?'
            redirect_url = f"{referer}{separator}new_contact_id={new_contact.id}&new_contact_name={new_contact.Name}&new_contact_type={new_contact.Type}"
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
