from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from .auth.utils import login_required, is_authorized, club_permission_required
from .auth.permissions import Permissions
from flask_login import current_user
from .club_context import get_current_club_id, authorized_club_required
from .models import User, Contact, AuthRole, PermissionAudit, ContactClub, Club, ExComm, UserClub, ExcommOfficer, MeetingRole
from . import db
from datetime import datetime
from .utils import process_club_logo

about_club_bp = Blueprint('about_club_bp', __name__)

@about_club_bp.route('/about_club')
@login_required
@authorized_club_required
def about_club():
    """Renders the About Club page."""
    if not is_authorized(Permissions.LIBRARY_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    # Get club from database using current context
    club_id = get_current_club_id()
    club = db.session.get(Club, club_id) if club_id else Club.query.first()
    
    # Get current excomm team from database.
    # Note: the IPP officer role is stored as 'IPP' in the DB (meeting_roles.name),
    # not 'Immediate Past President'. All lookups must use the stored name.
    excomm = None
    excomm_team = {
        'name': '',
        'term': '',
        'members': {
            'President': '', 'VPE': '', 'VPM': '', 'VPPR': '',
            'Secretary': '', 'Treasurer': '', 'SAA': '', 'IPP': ''
        }
    }

    if club:
        # Prefer the pinned current excomm; fall back to the most recent term.
        if club.current_excomm_id:
            excomm = ExComm.query.get(club.current_excomm_id)
        if not excomm:
            excomm = ExComm.query.filter_by(club_id=club.id).order_by(ExComm.start_date.desc()).first()

        if excomm:
            # Use get_officers() which returns {role_name: Contact}
            active_officers = excomm.get_officers()

            excomm_team = {
                'name': excomm.excomm_name or '',
                'term': excomm.excomm_term or '',
                'members': {
                    'President': active_officers['President'].Name if active_officers.get('President') else '',
                    'VPE': active_officers['VPE'].Name if active_officers.get('VPE') else '',
                    'VPM': active_officers['VPM'].Name if active_officers.get('VPM') else '',
                    'VPPR': active_officers['VPPR'].Name if active_officers.get('VPPR') else '',
                    'Secretary': active_officers['Secretary'].Name if active_officers.get('Secretary') else '',
                    'Treasurer': active_officers['Treasurer'].Name if active_officers.get('Treasurer') else '',
                    'SAA': active_officers['SAA'].Name if active_officers.get('SAA') else '',
                    'IPP': active_officers['IPP'].Name if active_officers.get('IPP') else '',
                }
            }

    # Get all member contacts for ExComm officer selection, filtered by club
    all_contacts = Contact.query.join(ContactClub).filter(
        ContactClub.club_id == (club.id if club else None),
        Contact.Type == 'Member'
    ).order_by(Contact.Name.asc()).all()
    contacts_list = [{'id': c.id, 'name': c.Name} for c in all_contacts]

    return render_template('about_club.html', club=club, excomm_team=excomm_team, contacts_list=contacts_list)


@about_club_bp.route('/about_club/update', methods=['POST'])
@login_required
@authorized_club_required
def about_club_update():
    """Update club settings from the about club page."""
    if not is_authorized(Permissions.CLUB_MANAGE):
        return jsonify(success=False, message="Permission denied"), 403
    
    try:
        data = request.get_json()
        
        # Get the club from current context
        club_id = get_current_club_id()
        club = db.session.get(Club, club_id)
        if not club:
            return jsonify(success=False, message="No club found"), 404
            
        # Update club fields
        if 'club_no' in data:
            club.club_no = data['club_no']
        if 'club_name' in data:
            club.club_name = data['club_name']
        if 'short_name' in data:
            club.short_name = data['short_name'] or None
        if 'district' in data:
            club.district = data['district'] or None
        if 'division' in data:
            club.division = data['division'] or None
        if 'area' in data:
            club.area = data['area'] or None
        if 'club_address' in data:
            club.club_address = data['club_address'] or None
        if 'meeting_date' in data:
            club.meeting_date = data['meeting_date'] or None
        if 'contact_phone_number' in data:
            club.contact_phone_number = data['contact_phone_number'] or None
        if 'website' in data:
            website = data['website'] or None
            if website and not (website.startswith('http://') or website.startswith('https://')):
                website = 'https://' + website
            club.website = website
        
        # Parse meeting time
        if 'meeting_time' in data and data['meeting_time']:
            try:
                club.meeting_time = datetime.strptime(data['meeting_time'], '%H:%M').time()
            except ValueError:
                return jsonify(success=False, message="Invalid meeting time format"), 400
        
        # Parse founded date
        if 'founded_date' in data and data['founded_date']:
            try:
                club.founded_date = datetime.strptime(data['founded_date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify(success=False, message="Invalid founded date format"), 400

        # Update ExComm fields
        excomm = None
        if club.current_excomm_id:
            excomm = db.session.get(ExComm, club.current_excomm_id)
            
        # Check if we have ANY ExComm-related data
        excomm_fields = ['excomm_name', 'excomm_term', 'excomm_president', 'excomm_vpe', 
                         'excomm_vpm', 'excomm_vppr', 'excomm_secretary', 'excomm_treasurer', 
                         'excomm_saa', 'excomm_ipp']
        has_excomm_data = any(field in data for field in excomm_fields)

        if has_excomm_data:
            if not excomm:
                # Create a new ExComm record if none exists
                now = datetime.now()
                default_term = f"{now.year % 100}{'H1' if now.month <= 6 else 'H2'}"
                
                excomm = ExComm(
                    club_id=club.id,
                    excomm_term=data.get('excomm_term') or default_term
                )
                db.session.add(excomm)
                db.session.flush() # Get ID
                club.current_excomm_id = excomm.id
            
            if 'excomm_name' in data:
                excomm.excomm_name = data['excomm_name'] or None
            if 'excomm_term' in data and data['excomm_term']:
                excomm.excomm_term = data['excomm_term']

            # Update ExComm Officers
            db_role_map = {
                'excomm_president': 'President',
                'excomm_vpe': 'VPE',
                'excomm_vpm': 'VPM',
                'excomm_vppr': 'VPPR',
                'excomm_secretary': 'Secretary',
                'excomm_treasurer': 'Treasurer',
                'excomm_saa': 'SAA',
                'excomm_ipp': 'Immediate Past President'
            }

            for field, role_name in db_role_map.items():
                if field in data:
                    contact_name = data[field]
                    
                    # Find MeetingRole object for this role
                    # We look up globally or for this club if overriding is supported,
                    # but typically ExComm roles are standard.
                    role_obj = MeetingRole.query.filter_by(name=role_name).first()
                    
                    # If this role doesn't exist in DB, skip it (shouldn't happen for std roles)
                    if not role_obj:
                        continue

                    # Look for existing ExcommOfficer entry
                    officer_entry = ExcommOfficer.query.filter_by(
                        excomm_id=excomm.id,
                        meeting_role_id=role_obj.id
                    ).first()

                    if contact_name:
                        contact = Contact.query.filter_by(Name=contact_name).first()
                        if contact:
                            if officer_entry:
                                officer_entry.contact_id = contact.id
                            else:
                                new_officer = ExcommOfficer(
                                    excomm_id=excomm.id,
                                    contact_id=contact.id,
                                    meeting_role_id=role_obj.id
                                )
                                db.session.add(new_officer)
                    else:
                        # Clear the officer if name is empty
                        if officer_entry:
                            db.session.delete(officer_entry)


        club.updated_at = datetime.utcnow()
        if excomm:
            excomm.updated_at = datetime.utcnow()
            
                # Continue with the rest of the update even if is_officer update fails

        db.session.commit()
        
        return jsonify(success=True, message="Settings updated successfully")
    
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@about_club_bp.route('/about_club/upload_logo', methods=['POST'])
@login_required
@authorized_club_required
def upload_club_logo():
    """Handle club logo upload."""
    if not is_authorized(Permissions.CLUB_MANAGE):
        return jsonify(success=False, message="Permission denied"), 403
    
    try:
        club_id = get_current_club_id()
        club = db.session.get(Club, club_id)
        if not club:
            return jsonify(success=False, message="No club found"), 404

        if 'logo' not in request.files:
             return jsonify(success=False, message="No file part"), 400
             
        file = request.files['logo']
        if file.filename == '':
             return jsonify(success=False, message="No selected file"), 400

        if file:
            logo_url = process_club_logo(file, club.id)
            if logo_url:
                club.logo_url = logo_url
                db.session.commit()
                return jsonify(success=True, message="Logo updated successfully", logo_url=url_for('static', filename=logo_url))
            else:
                return jsonify(success=False, message="Error processing image"), 500
                
        return jsonify(success=False, message="Unknown error"), 500
        
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@about_club_bp.route('/excomm')
@login_required
@authorized_club_required
@club_permission_required(Permissions.CLUB_VIEW)
def excomm_page():
    """Renders the Excomm page showing past terms and contact cards."""
    club_id = get_current_club_id()
    club = db.session.get(Club, club_id) if club_id else Club.query.first()
    
    # 1. Fetch all excomm terms for the club, sorted by start_date descending
    # Eager-load officers and related roles/contacts to prevent N+1 queries in sidebar serialization
    excomm_list = []
    if club:
        excomm_list = ExComm.query.options(
            db.joinedload(ExComm.officers).joinedload(ExcommOfficer.contact),
            db.joinedload(ExComm.officers).joinedload(ExcommOfficer.meeting_role)
        ).filter_by(club_id=club.id).order_by(ExComm.start_date.desc()).all()
        
    # 2. Identify the selected Excomm term
    selected_excomm = None
    term_id = request.args.get('term_id', type=int)
    
    if term_id:
        selected_excomm = ExComm.query.filter_by(id=term_id, club_id=club.id).first()
    elif club and club.current_excomm_id:
        selected_excomm = ExComm.query.get(club.current_excomm_id)
        
    # Fallback to the most recent term if none selected/current
    if not selected_excomm and excomm_list:
        selected_excomm = excomm_list[0]
        
    # 3. Fetch officer roles and sort them in the correct order
    all_roles = MeetingRole.get_all_for_club(club.id if club else None)
    officer_roles = [r for r in all_roles if r.type == 'officer']
    if not officer_roles:
        standard_officers = ['President', 'VPE', 'VPM', 'VPPR', 'Secretary', 'Treasurer', 'SAA', 'Immediate Past President']
        officer_roles = [r for r in all_roles if r.name in standard_officers]
        
    role_order = {
        'President': 0,
        'VPE': 1,
        'VPM': 2,
        'VPPR': 3,
        'Secretary': 4,
        'Treasurer': 5,
        'SAA': 6,
        'Immediate Past President': 7
    }
    officer_roles.sort(key=lambda r: role_order.get(r.name, 999))
    
    # 4. Group and sort the actual officers for the selected term
    primary_officers = []
    assistant_officers = []
    
    if selected_excomm:
        # Group by role name
        role_to_officers = {}
        # Fetch officer assignments with eager loaded contacts/roles to prevent N+1 queries
        officer_links = ExcommOfficer.query.options(
            db.joinedload(ExcommOfficer.contact),
            db.joinedload(ExcommOfficer.meeting_role)
        ).filter_by(excomm_id=selected_excomm.id).all()
        for o in officer_links:
            role_name = o.meeting_role.name
            if role_name not in role_to_officers:
                role_to_officers[role_name] = []
            role_to_officers[role_name].append(o)
            
        # Add primary officers in sorted role order
        for role in officer_roles:
            role_links = role_to_officers.get(role.name, [])
            primary = next((o for o in role_links if not o.is_assistant), None)
            if primary:
                primary_officers.append(primary)
                
        # Add assistant officers in sorted role order
        for role in officer_roles:
            role_links = role_to_officers.get(role.name, [])
            assistants = [o for o in role_links if o.is_assistant]
            assistant_officers.extend(assistants)
            
    # 5. Fetch all contacts for ExComm officer selection
    all_contacts = []
    if club:
        all_contacts = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == club.id
        ).order_by(Contact.Name.asc()).all()
    contacts_list = [{'id': c.id, 'Name': c.Name} for c in all_contacts]
    
    return render_template(
        'excomm.html',
        club=club,
        excomm_list=excomm_list,
        selected_excomm=selected_excomm,
        primary_officers=primary_officers,
        assistant_officers=assistant_officers,
        officer_roles=officer_roles,
        contacts_list=contacts_list,
        Permissions=Permissions
    )

