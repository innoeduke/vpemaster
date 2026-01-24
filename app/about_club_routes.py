from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user
from .club_context import get_current_club_id, authorized_club_required
from .models import User, Contact, AuthRole, PermissionAudit, ContactClub, Club, ExComm, UserClub
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
            excomm_team = {
                'name': excomm.excomm_name or '',
                'term': excomm.excomm_term or '',
                'members': {
                    'President': excomm.president.Name if excomm.president else '',
                    'VPE': excomm.vpe.Name if excomm.vpe else '',
                    'VPM': excomm.vpm.Name if excomm.vpm else '',
                    'VPPR': excomm.vppr.Name if excomm.vppr else '',
                    'Secretary': excomm.secretary.Name if excomm.secretary else '',
                    'Treasurer': excomm.treasurer.Name if excomm.treasurer else '',
                    'SAA': excomm.saa.Name if excomm.saa else '',
                    'IPP': excomm.ipp.Name if excomm.ipp else ''
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
                # Determine a default term if not provided (e.g., current year + H1/H2)
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
            officer_roles = {
                'excomm_president': 'president_id',
                'excomm_vpe': 'vpe_id',
                'excomm_vpm': 'vpm_id',
                'excomm_vppr': 'vppr_id',
                'excomm_secretary': 'secretary_id',
                'excomm_treasurer': 'treasurer_id',
                'excomm_saa': 'saa_id',
                'excomm_ipp': 'ipp_id'
            }

            for field, model_attr in officer_roles.items():
                if field in data:
                    officer_name = data[field]
                    if not officer_name:
                        setattr(excomm, model_attr, None)
                    else:
                        contact = Contact.query.filter_by(Name=officer_name).first()
                        if contact:
                            setattr(excomm, model_attr, contact.id)
                        else:
                            # If contact not found, maybe ignore or set to None
                            setattr(excomm, model_attr, None)

        club.updated_at = datetime.utcnow()
        if excomm:
            excomm.updated_at = datetime.utcnow()
            
            # Check and add Staff role for ExComm members
            try:
                staff_role = AuthRole.query.filter_by(name=Permissions.STAFF).first()
                if staff_role:
                    # Collect unique contact IDs from current excomm officers
                    officer_contact_ids = set()
                    officer_positions = ['president_id', 'vpe_id', 'vpm_id', 'vppr_id', 
                                      'secretary_id', 'treasurer_id', 'saa_id', 'ipp_id']
                    for attr in officer_positions:
                        cid = getattr(excomm, attr)
                        if cid:
                            officer_contact_ids.add(cid)
                    
                    if officer_contact_ids:
                        # Find UserClub records for these contacts in this club
                        ucs = UserClub.query.filter(
                            UserClub.contact_id.in_(list(officer_contact_ids)),
                            UserClub.club_id == club.id
                        ).all()
                        
                        for uc in ucs:
                            if uc.user_id:
                                # Check if user needs the Staff role (has no role or lower role than Staff)
                                current_role = None
                                # Grant the new role
                                if uc.club_role_level:
                                    # Check if they already have this specific role level
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
