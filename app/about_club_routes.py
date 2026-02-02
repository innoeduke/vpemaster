from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from .auth.utils import login_required, is_authorized
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
    if not is_authorized(Permissions.ABOUT_CLUB_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    # Get club from database using current context
    club_id = get_current_club_id()
    club = db.session.get(Club, club_id) if club_id else Club.query.first()
    
    # Get current excomm team from database
    excomm = None
    excomm_team = {
        'name': '', 
        'term': '', 
        'members': {
            'President': '', 'VPE': '', 'VPM': '', 'VPPR': '', 
            'Secretary': '', 'Treasurer': '', 'SAA': '', 'IPP': ''
        }
    }
    
    if club and club.current_excomm_id:
        excomm = ExComm.query.get(club.current_excomm_id)
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
                    'IPP': active_officers['IPP'].Name if active_officers.get('IPP') else ''
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
    if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
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
                'excomm_ipp': 'IPP'
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
            
            # Check and add Staff role for ExComm members
            try:
                staff_role = AuthRole.query.filter_by(name=Permissions.STAFF).first()
                if staff_role:
                    # Collect unique contact IDs from current excomm officers
                    officer_contact_ids = set()
                    
                    # Reload officers to get latest state from DB session
                    # Since we modified the session but haven't committed, 
                    # we must rely on what we just did or flush.
                    # Simplest is to flush and re-query ExcommOfficer table for this excomm
                    db.session.flush()
                    
                    current_officers = ExcommOfficer.query.filter_by(excomm_id=excomm.id).all()
                    for officer in current_officers:
                        officer_contact_ids.add(officer.contact_id)
                    
                    if officer_contact_ids:
                        # Find UserClub records for these contacts in this club
                        ucs = UserClub.query.filter(
                            UserClub.contact_id.in_(list(officer_contact_ids)),
                            UserClub.club_id == club.id
                        ).all()
                        
                        for uc in ucs:
                            if uc.user_id:
                                # Check if user needs the Staff role
                                if uc.club_role_level:
                                    if not (uc.club_role_level & staff_role.level):
                                        uc.club_role_level |= staff_role.level
                                else:
                                    uc.club_role_level = staff_role.level
                                    
                                    # Audit log for auto-upgrade
                                    audit = PermissionAudit(
                                        admin_id=current_user.id,
                                        action='AUTO_UPGRADE_EXCOMM_STAFF',
                                        target_type='USER',
                                        target_id=uc.user_id,
                                        target_name=uc.user.username if uc.user else f"User {uc.user_id}",
                                        changes=f"Auto-assigned Staff role to ExComm officer in club {club.id}"
                                    )
                                    db.session.add(audit)
            except Exception as role_err:
                current_app.logger.error(f"Error during ExComm role upgrade: {str(role_err)}")
                # Continue with the rest of the update even if role upgrade fails

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
    if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
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

