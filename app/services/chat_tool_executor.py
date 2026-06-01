from datetime import datetime, date
import json
from app import db
from app.models import (
    Meeting, Contact, SessionLog, SessionType, MeetingRole, 
    ChatMessage, Achievement, Roster, Ticket, Vote, ContactClub,
    ContactPath, Pathway, User, UserClub
)
from app.auth.permissions import Permissions
from app.auth.utils import is_authorized
from app.services.role_service import RoleService
from app.services.achievement_service import AchievementService
from flask import current_app, url_for
from sqlalchemy import func, or_

class ChatToolExecutor:
    """
    Executes business logic for chat commands and AI tools.
    All methods perform underlying permission checks before executing.
    """

    @staticmethod
    def resolve_meeting(meeting_identifier, club_id):
        """
        Resolves meeting_identifier (e.g. '350', '#350', '2026-06-15') to a Meeting object.
        """
        if not meeting_identifier:
            return None
            
        ident = str(meeting_identifier).strip().lstrip('#')
        
        # Try meeting number (integer)
        try:
            mtg_num = int(ident)
            query = Meeting.query.filter_by(Meeting_Number=mtg_num)
            if club_id:
                query = query.filter_by(club_id=club_id)
            meeting = query.first()
            if meeting:
                return meeting
        except ValueError:
            pass
            
        # Try date format YYYY-MM-DD
        try:
            mtg_date = datetime.strptime(ident, '%Y-%m-%d').date()
            query = Meeting.query.filter_by(Meeting_Date=mtg_date)
            if club_id:
                query = query.filter_by(club_id=club_id)
            meeting = query.first()
            if meeting:
                return meeting
        except ValueError:
            pass
            
        return None

    @staticmethod
    def resolve_contact(contact_name, club_id):
        """
        Resolves a contact by name.
        """
        if not contact_name:
            return None
            
        name = str(contact_name).strip()
        
        # Search exact match
        query = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == club_id,
            Contact.Name == name
        )
        contact = query.first()
        if contact:
            return contact
            
        # Search partial match case insensitive
        query = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == club_id,
            Contact.Name.ilike(f"%{name}%")
        )
        contacts = query.all()
        if len(contacts) == 1:
            return contacts[0]
            
        # Try splitting parts
        parts = name.split()
        if len(parts) >= 2:
            first_name, last_name = parts[0], parts[-1]
            query = Contact.query.join(ContactClub).filter(
                ContactClub.club_id == club_id,
                Contact.first_name.ilike(first_name),
                Contact.last_name.ilike(last_name)
            )
            contact = query.first()
            if contact:
                return contact
                
        return None

    @staticmethod
    def resolve_session_log(meeting_id, role_name, club_id):
        """
        Resolves a session log in a meeting for a role name.
        """
        norm_name = str(role_name).strip().lower().replace('-', '').replace(' ', '')
        
        logs = SessionLog.query.join(SessionType).join(MeetingRole).filter(
            SessionLog.meeting_id == meeting_id
        ).all()
        
        # Exact match check
        for log in logs:
            if log.session_type and log.session_type.role:
                r_name = log.session_type.role.name.strip().lower().replace('-', '').replace(' ', '')
                if r_name == norm_name:
                    return log
                    
        # Partial match check
        for log in logs:
            if log.session_type and log.session_type.role:
                r_name = log.session_type.role.name.strip().lower().replace('-', '').replace(' ', '')
                if norm_name in r_name or r_name in norm_name:
                    return log
                    
        return None

    @classmethod
    def execute(cls, tool_name, params, user, club_id):
        """
        Routes the tool name to the appropriate method.
        Returns a dictionary indicating status: {'success': bool, 'message': str, ...}
        """
        method = getattr(cls, f"tool_{tool_name}", None)
        if not method:
            return {'success': False, 'message': f"Unknown tool '{tool_name}'."}
        try:
            return method(params, user, club_id)
        except Exception as e:
            current_app.logger.error(f"Error executing chat tool {tool_name}: {str(e)}")
            return {'success': False, 'message': f"Internal error during execution: {str(e)}"}

    # --- Tool Implementations ---

    @classmethod
    def tool_create_meeting(cls, params, user, club_id):
        if not is_authorized(Permissions.AGENDA_CREATE):
            return {'success': False, 'message': "You do not have permission to create meetings (AGENDA_CREATE)."}
            
        meeting_date_str = params.get('date')
        template_name = params.get('template_name')
        
        if not meeting_date_str:
            return {'success': False, 'message': "Meeting date is required (YYYY-MM-DD)."}
            
        try:
            meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
        except ValueError:
            return {'success': False, 'message': "Invalid date format. Use YYYY-MM-DD."}
            
        # Get template listing
        type_to_template = Meeting.get_type_to_template(club_id)
        
        if not template_name:
            # List templates and request selection
            return {
                'success': False,
                'need_template': True,
                'templates': list(type_to_template.keys()),
                'message': "Please specify a meeting template. Available options: " + ", ".join(type_to_template.keys())
            }
            
        template_file = type_to_template.get(template_name)
        if not template_file:
            # Fuzzy match template
            norm_tpl = template_name.lower().replace(' ', '')
            found = None
            for k, v in type_to_template.items():
                if norm_tpl in k.lower().replace(' ', ''):
                    found = k
                    template_file = v
                    break
            if not found:
                return {
                    'success': False,
                    'need_template': True,
                    'templates': list(type_to_template.keys()),
                    'message': f"Invalid template '{template_name}'. Available options: " + ", ".join(type_to_template.keys())
                }
            template_name = found

        # Determine meeting number (most recent + 1)
        most_recent = Meeting.query.filter_by(club_id=club_id).order_by(Meeting.Meeting_Number.desc()).first()
        meeting_number = (most_recent.Meeting_Number + 1) if most_recent else 1
        
        # Create meeting
        from app.agenda_routes import _get_or_create_media_id, _upsert_meeting_record, _generate_logs_from_template
        
        data = {
            'meeting_id': None,
            'meeting_number': meeting_number,
            'meeting_date': meeting_date,
            'start_time': datetime.strptime("19:00", "%H:%M").time(), # Default start time
            'meeting_type': template_name,
            'ge_mode': 0,
            'meeting_title': f"Meeting #{meeting_number}",
            'subtitle': None,
            'wod': None,
            'media_url': None,
            'template_file': template_file
        }
        
        try:
            meeting = _upsert_meeting_record(data, None)
            meeting.club_id = club_id
            db.session.commit()
            
            _generate_logs_from_template(meeting, template_file)
            db.session.commit()
            
            redirect_url = url_for('agenda_bp.agenda', meeting_id=meeting.id, _external=True)
            return {
                'success': True,
                'message': f"Successfully created Meeting #{meeting_number} for {meeting_date_str} using template '{template_name}'.",
                'meeting_id': meeting.id,
                'meeting_number': meeting_number,
                'redirect_url': redirect_url
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Failed to create meeting: {str(e)}"}

    @classmethod
    def tool_assign_role(cls, params, user, club_id):
        if not is_authorized(Permissions.BOOKING_ASSIGN_ALL):
            return {'success': False, 'message': "You do not have permission to assign roles (BOOKING_ASSIGN_ALL)."}
            
        meeting_ident = params.get('meeting_identifier')
        role_name = params.get('role_name')
        contact_name = params.get('contact_name')
        
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        contact = cls.resolve_contact(contact_name, club_id)
        if not contact:
            return {'success': False, 'message': f"Contact '{contact_name}' not found."}
            
        log = cls.resolve_session_log(meeting.id, role_name, club_id)
        if not log:
            return {'success': False, 'message': f"Role '{role_name}' not found in Meeting #{meeting.Meeting_Number} agenda."}
            
        try:
            RoleService.assign_meeting_role(log, [contact.id], is_admin=True)
            db.session.commit()
            return {
                'success': True,
                'message': f"Successfully assigned {contact.Name} as {log.session_type.role.name} for Meeting #{meeting.Meeting_Number}."
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Failed to assign role: {str(e)}"}

    @classmethod
    def tool_cancel_role(cls, params, user, club_id):
        if not is_authorized(Permissions.BOOKING_ASSIGN_ALL):
            return {'success': False, 'message': "You do not have permission to cancel role assignments (BOOKING_ASSIGN_ALL)."}
            
        meeting_ident = params.get('meeting_identifier')
        role_name = params.get('role_name')
        contact_name = params.get('contact_name')
        
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        contact = cls.resolve_contact(contact_name, club_id)
        if not contact:
            return {'success': False, 'message': f"Contact '{contact_name}' not found."}
            
        log = cls.resolve_session_log(meeting.id, role_name, club_id)
        if not log:
            return {'success': False, 'message': f"Role '{role_name}' not found in Meeting #{meeting.Meeting_Number} agenda."}
            
        try:
            success, msg = RoleService.cancel_meeting_role(log, contact.id, is_admin=True)
            if success:
                db.session.commit()
                return {'success': True, 'message': f"Successfully cancelled assignment for {contact.Name} as {log.session_type.role.name}."}
            else:
                return {'success': False, 'message': f"Failed to cancel role: {msg}"}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Error during cancellation: {str(e)}"}

    @classmethod
    def tool_add_contact(cls, params, user, club_id):
        if not (is_authorized(Permissions.CONTACT_BOOK_EDIT) or is_authorized(Permissions.CONTACT_ADD_GUEST)):
            return {'success': False, 'message': "You do not have permission to add contacts (CONTACT_ADD_GUEST)."}
            
        name = params.get('name')
        email = params.get('email')
        phone = params.get('phone')
        
        if not name:
            return {'success': False, 'message': "Name is required."}
            
        # Duplicate Checks
        dup_name = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id, Contact.Name == name).first()
        if dup_name:
            return {'success': False, 'message': f"A contact with name '{name}' already exists in this club."}
            
        if email:
            dup_email = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id, Contact.Email == email).first()
            if dup_email:
                return {'success': False, 'message': f"A contact with email '{email}' already exists in this club."}
                
        if phone:
            dup_phone = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id, Contact.Phone_Number == phone).first()
            if dup_phone:
                return {'success': False, 'message': f"A contact with phone '{phone}' already exists in this club."}

        try:
            new_contact = Contact(
                Name=name,
                Email=email,
                Phone_Number=phone,
                Type='Guest', # Always create as Guest per standard route rules
                Date_Created=date.today()
            )
            db.session.add(new_contact)
            db.session.flush()
            
            # Link club
            club_link = ContactClub(contact_id=new_contact.id, club_id=club_id, is_officer=False)
            db.session.add(club_link)
            db.session.commit()
            
            return {
                'success': True,
                'message': f"Successfully created guest contact '{name}'.",
                'contact_id': new_contact.id
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Failed to add contact: {str(e)}"}

    @classmethod
    def tool_check_in(cls, params, user, club_id):
        if not is_authorized(Permissions.ROSTER_EDIT):
            return {'success': False, 'message': "You do not have permission to check in contacts (ROSTER_EDIT)."}
            
        meeting_ident = params.get('meeting_identifier')
        contact_name = params.get('contact_name')
        ticket_type = params.get('ticket_type')
        
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        contact = cls.resolve_contact(contact_name, club_id)
        if not contact:
            return {'success': False, 'message': f"Contact '{contact_name}' not found."}
            
        # Determine ticket
        ticket_name = ticket_type
        if not ticket_name:
            # Auto-detect ticket name
            contact_club = ContactClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
            if contact_club and contact_club.is_officer:
                ticket_name = 'Officer'
            elif contact.Type == 'Member':
                ticket_name = 'Early-bird' # Default member ticket
            else:
                ticket_name = 'Walk-in' # Default guest ticket

        ticket = Ticket.query.filter_by(name=ticket_name, club_id=club_id).first()
        if not ticket:
            ticket = Ticket.query.filter_by(name='Walk-in', club_id=club_id).first()
            
        if not ticket:
            return {'success': False, 'message': f"No valid ticket template found for checking in."}

        try:
            # Roster lookup
            entry = Roster.query.filter_by(meeting_id=meeting.id, contact_id=contact.id).first()
            if entry:
                entry.ticket_id = ticket.id
                entry.contact_type = 'Officer' if ticket.name == 'Officer' else ('Member' if contact.Type == 'Member' else 'Guest')
                entry.check_in_time = datetime.utcnow()
            else:
                entry = Roster(
                    meeting_id=meeting.id,
                    contact_id=contact.id,
                    ticket_id=ticket.id,
                    contact_type='Officer' if ticket.name == 'Officer' else ('Member' if contact.Type == 'Member' else 'Guest'),
                    check_in_time=datetime.utcnow(),
                    quantity=1
                )
                db.session.add(entry)
                
            db.session.commit()
            return {
                'success': True,
                'message': f"Successfully checked in {contact.Name} for Meeting #{meeting.Meeting_Number} with ticket '{ticket.name}'."
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Check-in failed: {str(e)}"}

    @classmethod
    def tool_complete_level(cls, params, user, club_id):
        if not is_authorized(Permissions.ACHIEVEMENTS_EDIT):
            return {'success': False, 'message': "You do not have permission to record achievements (ACHIEVEMENTS_EDIT)."}
            
        contact_name = params.get('contact_name')
        pathway_name = params.get('pathway_name')
        level = params.get('level')
        issue_date_str = params.get('issue_date')
        
        contact = cls.resolve_contact(contact_name, club_id)
        if not contact:
            return {'success': False, 'message': f"Contact '{contact_name}' not found."}
            
        # Find user account (achievements are associated with users, not contacts)
        contact_user_id = contact.user_id
        if not contact_user_id:
            # See if we can locate a user link
            user_club = UserClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
            if user_club:
                contact_user_id = user_club.user_id
        
        if not contact_user_id:
            return {'success': False, 'message': f"Contact '{contact.Name}' is not linked to a user account, cannot record achievements."}

        # Resolve pathway name from standard list
        # Pathways might have standard abbreviations or full names
        pathway = Pathway.query.filter(
            or_(Pathway.name.ilike(pathway_name), Pathway.abbr.ilike(pathway_name))
        ).first()
        
        if not pathway:
            return {'success': False, 'message': f"Pathway '{pathway_name}' not found in pathway library."}

        try:
            level_num = int(level)
            if level_num < 1 or level_num > 5:
                raise ValueError()
        except ValueError:
            return {'success': False, 'message': "Level must be an integer between 1 and 5."}

        issue_date = date.today()
        if issue_date_str:
            try:
                issue_date = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
            except ValueError:
                return {'success': False, 'message': "Invalid date format. Use YYYY-MM-DD."}

        try:
            # Check if this achievement already exists
            existing = Achievement.query.filter_by(
                user_id=contact_user_id,
                achievement_type='level-completion',
                path_name=pathway.name,
                level=level_num
            ).first()
            
            if existing:
                return {'success': False, 'message': f"Achievement {pathway.name} Level {level_num} already recorded for {contact.Name}."}

            # Record
            AchievementService.record_achievement(
                user_id=contact_user_id,
                requestor_id=user.id,
                achievement_type='level-completion',
                issue_date=issue_date,
                path_name=pathway.name,
                level=level_num,
                notes=f"Recorded via AI Assistant"
            )
            
            # Ensure contact pathway is registered as working or completed
            c_path = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
            if not c_path:
                c_path = ContactPath(contact_id=contact.id, path_id=pathway.id, status='working', registered_date=date.today())
                db.session.add(c_path)
            
            if level_num == 5:
                c_path.status = 'completed'
                c_path.completed_date = date.today()
                
            db.session.commit()
            return {
                'success': True,
                'message': f"Successfully recorded Level {level_num} completion in '{pathway.name}' for {contact.Name}. Lower levels auto-added if missing."
            }
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Failed to record achievement: {str(e)}"}

    @classmethod
    def tool_get_pathway_status(cls, params, user, club_id):
        if not is_authorized(Permissions.ACHIEVEMENTS_VIEW):
            return {'success': False, 'message': "You do not have permission to view achievements (ACHIEVEMENTS_VIEW)."}
            
        contact_name = params.get('contact_name')
        
        contact = cls.resolve_contact(contact_name, club_id)
        if not contact:
            return {'success': False, 'message': f"Contact '{contact_name}' not found."}
            
        registered_paths = ContactPath.query.filter_by(contact_id=contact.id).all()
        
        # Locate user achievements
        contact_user_id = contact.user_id
        if not contact_user_id:
            user_club = UserClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
            if user_club:
                contact_user_id = user_club.user_id
                
        achievements = []
        if contact_user_id:
            achievements = Achievement.query.filter_by(
                user_id=contact_user_id,
                achievement_type='level-completion'
            ).order_by(Achievement.path_name, Achievement.level).all()

        ach_map = {}
        for ach in achievements:
            if ach.path_name not in ach_map:
                ach_map[ach.path_name] = []
            ach_map[ach.path_name].append(ach.level)

        summary = f"Pathway status for **{contact.Name}**:\n"
        if not registered_paths:
            summary += "* Not currently registered for any pathways."
            return {'success': True, 'message': summary}

        for rp in registered_paths:
            path_name = rp.pathway.name
            completed_levels = ach_map.get(path_name, [])
            levels_str = ", ".join(f"L{lvl}" for lvl in sorted(completed_levels)) if completed_levels else "None"
            status_emoji = "✅" if rp.status == 'completed' else "⏳"
            summary += f"* {status_emoji} **{path_name}** ({rp.status}) - Completed levels: `{levels_str}`\n"
            
        return {'success': True, 'message': summary}

    @classmethod
    def tool_search_contacts(cls, params, user, club_id):
        name = params.get('name')
        if not name:
            return {'success': False, 'message': "Search term is required."}
            
        query = Contact.query.join(ContactClub).filter(
            ContactClub.club_id == club_id,
            Contact.Name.ilike(f"%{name}%")
        )
        contacts = query.limit(10).all()
        
        if not contacts:
            return {'success': True, 'message': f"No contacts found matching '{name}'."}
            
        res = f"Found {len(contacts)} contacts:\n"
        for c in contacts:
            res += f"* **{c.Name}** ({c.Type}) - Email: {c.Email or 'N/A'}, Phone: {c.Phone_Number or 'N/A'}\n"
        return {'success': True, 'message': res}

    @classmethod
    def tool_get_meeting_info(cls, params, user, club_id):
        if not is_authorized(Permissions.AGENDA_VIEW):
            return {'success': False, 'message': "You do not have permission to view meetings (AGENDA_VIEW)."}
            
        meeting_ident = params.get('meeting_identifier')
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        agenda_url = url_for('agenda_bp.agenda', meeting_id=meeting.id, _external=True)
        
        info = (
            f"**Meeting #{meeting.Meeting_Number} Details**\n"
            f"* **Title**: {meeting.Meeting_Title or 'N/A'}\n"
            f"* **Subtitle**: {meeting.Subtitle or 'N/A'}\n"
            f"* **Date**: {meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting.Meeting_Date else 'N/A'}\n"
            f"* **Start Time**: {meeting.Start_Time.strftime('%H:%M') if meeting.Start_Time else 'N/A'}\n"
            f"* **Theme/Type**: {meeting.type}\n"
            f"* **Word of the Day**: {meeting.WOD or 'N/A'}\n"
            f"* **Status**: `{meeting.status}`\n"
            f"* **Manager**: {meeting.manager.Name if meeting.manager else 'N/A'}\n"
            f"* **Link**: [Open Agenda]({agenda_url})"
        )
        return {'success': True, 'message': info}

    @classmethod
    def tool_list_meetings(cls, params, user, club_id):
        if not is_authorized(Permissions.AGENDA_VIEW):
            return {'success': False, 'message': "You do not have permission to view meetings (AGENDA_VIEW)."}
            
        status = params.get('status')
        limit = params.get('limit', 5)
        
        try:
            limit = int(limit)
        except ValueError:
            limit = 5
            
        query = Meeting.query.filter_by(club_id=club_id)
        if status:
            query = query.filter_by(status=status)
            
        meetings = query.order_by(Meeting.Meeting_Date.desc()).limit(limit).all()
        
        if not meetings:
            return {'success': True, 'message': "No meetings found."}
            
        res = f"Meetings list (showing up to {limit}):\n"
        for m in meetings:
            m_date = m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else 'N/A'
            agenda_url = url_for('agenda_bp.agenda', meeting_id=m.id, _external=True)
            res += f"* **Meeting #{m.Meeting_Number}** ({m_date}) - `{m.status}` - {m.Meeting_Title or m.type} [[Agenda]({agenda_url})]\n"
        return {'success': True, 'message': res}

    @classmethod
    def tool_get_role_assignments(cls, params, user, club_id):
        if not is_authorized(Permissions.BOOKING_VIEW_ALL):
            return {'success': False, 'message': "You do not have permission to view role assignments (BOOKING_VIEW_ALL)."}
            
        meeting_ident = params.get('meeting_identifier')
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        roles_list = RoleService.get_meeting_roles(meeting.id, club_id)
        
        res = f"Role assignments for **Meeting #{meeting.Meeting_Number}**:\n"
        assigned_count = 0
        
        for r in roles_list:
            if r.get('has_single_owner'):
                if r.get('owner_name'):
                    res += f"* **{r['role']}**: {r['owner_name']}\n"
                    assigned_count += 1
            else:
                owners = r.get('all_owners', [])
                if owners:
                    names = ", ".join(o['name'] for o in owners)
                    res += f"* **{r['role']}**: {names}\n"
                    assigned_count += len(owners)
                    
        if assigned_count == 0:
            res += "* No roles assigned yet."
            
        return {'success': True, 'message': res}

    @classmethod
    def tool_get_available_roles(cls, params, user, club_id):
        if not is_authorized(Permissions.BOOKING_VIEW_ALL):
            return {'success': False, 'message': "You do not have permission to view role assignments (BOOKING_VIEW_ALL)."}
            
        meeting_ident = params.get('meeting_identifier')
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        roles_list = RoleService.get_meeting_roles(meeting.id, club_id)
        
        res = f"Available (unassigned) roles for **Meeting #{meeting.Meeting_Number}**:\n"
        available_count = 0
        
        for r in roles_list:
            if r.get('has_single_owner'):
                if not r.get('owner_name'):
                    res += f"* **{r['role']}**\n"
                    available_count += 1
            else:
                owners = r.get('all_owners', [])
                if not owners:
                    res += f"* **{r['role']}**\n"
                    available_count += 1
                    
        if available_count == 0:
            res += "* All roles are fully booked!"
            
        return {'success': True, 'message': res}

    @classmethod
    def tool_update_meeting_status(cls, params, user, club_id):
        meeting_ident = params.get('meeting_identifier')
        new_status = params.get('status')
        
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        if not new_status:
            return {'success': False, 'message': "New status is required."}
            
        new_status = str(new_status).strip().lower()
        valid_statuses = ['unpublished', 'not started', 'running', 'finished', 'cancelled']
        if new_status not in valid_statuses:
            return {'success': False, 'message': f"Invalid status '{new_status}'. Valid values: " + ", ".join(valid_statuses)}

        # Check permission based on status transition
        # Typically changing status requires AGENDA_EDIT
        if not is_authorized(Permissions.AGENDA_EDIT):
            return {'success': False, 'message': "You do not have permission to modify meetings (AGENDA_EDIT)."}
            
        if new_status == 'cancelled' and not is_authorized(Permissions.AGENDA_DELETE):
            return {'success': False, 'message': "Cancelling/deleting a meeting requires agenda deletion permission (AGENDA_DELETE)."}

        try:
            old_status = meeting.status
            
            # Implement status transition side effects matching routes logic
            if new_status == 'finished' and old_status != 'finished':
                # Tally votes & clean waitlists
                from app.agenda_routes import _tally_votes_and_set_winners
                from app.models.roster import Waitlist
                from app.models.planner import Planner
                
                _tally_votes_and_set_winners(meeting)
                Waitlist.delete_for_meeting(meeting.id)
                
                plans = Planner.query.filter_by(meeting_id=meeting.id).all()
                for plan in plans:
                    if plan.status == 'booked':
                        plan.status = 'completed'
                    elif plan.status == 'waitlist':
                        plan.status = 'obsolete'
                        
                for log in meeting.session_logs:
                    is_prepared_speech = log.project and log.project.is_prepared_speech
                    is_project = (log.session_type and log.session_type.Valid_for_Project and log.Project_ID and log.Project_ID != 1) or is_prepared_speech
                    if is_project:
                        log.Status = 'Completed'
                        for owner in log.owners:
                            from app.utils import sync_contact_metadata
                            sync_contact_metadata(owner.id, commit=False)

            meeting.status = new_status
            db.session.commit()
            
            RoleService._clear_meeting_cache(meeting.id)
            return {'success': True, 'message': f"Successfully updated Meeting #{meeting.Meeting_Number} status from '{old_status}' to '{new_status}'."}
        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f"Failed to update meeting status: {str(e)}"}

    @classmethod
    def tool_get_voting_results(cls, params, user, club_id):
        meeting_ident = params.get('meeting_identifier')
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}

        # Check permissions
        is_running = (meeting.status == 'running')
        if is_running:
            if not is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=meeting):
                return {'success': False, 'message': "You do not have permission to track running voting results (VOTING_TRACK_PROGRESS)."}
        else:
            if not is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=meeting):
                return {'success': False, 'message': "You do not have permission to view voting results (VOTING_VIEW_RESULTS)."}

        # Query votes
        vote_counts = db.session.query(
            Vote.award_category,
            Contact.Name,
            func.count(Vote.id).label('vote_count')
        ).join(Contact, Vote.contact_id == Contact.id)\
         .filter(Vote.meeting_id == meeting.id)\
         .group_by(Vote.award_category, Contact.Name)\
         .all()

        # Format results
        cat_map = {}
        for category, contact_name, count in vote_counts:
            if not category:
                continue
            if category not in cat_map:
                cat_map[category] = []
            cat_map[category].append((contact_name, count))

        res = f"Voting results for **Meeting #{meeting.Meeting_Number}** ({meeting.status}):\n"
        if not vote_counts:
            res += "* No votes have been cast yet."
            return {'success': True, 'message': res}

        for cat, candidates in cat_map.items():
            # Sort candidates by vote count descending
            sorted_candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
            res += f"\n**Best {cat.capitalize().replace('-', ' ')}**:\n"
            for name, count in sorted_candidates:
                res += f"* {name}: {count} vote(s)\n"

        # Stored winners (for finished meetings)
        if meeting.status == 'finished':
            res += "\n🏆 **Official Award Winners**:\n"
            awards = [
                ('Speaker', meeting.best_speaker_id),
                ('Evaluator', meeting.best_evaluator_id),
                ('Table Topics Speaker', meeting.best_table_topic_id),
                ('Role Taker', meeting.best_role_taker_id)
            ]
            for title, cid in awards:
                if cid:
                    contact = db.session.get(Contact, cid)
                    if contact:
                        res += f"* Best {title}: **{contact.Name}**\n"
                        
        return {'success': True, 'message': res}
