from datetime import datetime, date
import json
from app import db
from app.models import (
    Meeting, Contact, SessionLog, SessionType, MeetingRole, 
    ChatMessage, Achievement, Roster, Ticket, Vote, ContactClub,
    ContactPath, Pathway, User, UserClub, Club, ExComm, ExcommOfficer,
    Project, PathwayProject
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
    def tool_get_meeting_agenda(cls, params, user, club_id):
        if not is_authorized(Permissions.AGENDA_VIEW):
            return {'success': False, 'message': "You do not have permission to view meetings (AGENDA_VIEW)."}
            
        meeting_ident = params.get('meeting_identifier')
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        logs = SessionLog.query.filter(
            SessionLog.meeting_id == meeting.id,
            SessionLog.state != 'cancelled'
        ).order_by(SessionLog.Meeting_Seq).all()
        
        from app.translations.translations import get_locale
        locale = get_locale()

        if not logs:
            msg = f"会议 #{meeting.Meeting_Number} 的日程表暂无内容。" if locale == 'zh_CN' else f"The agenda for Meeting #{meeting.Meeting_Number} has no items."
            return {'success': True, 'message': msg}
            
        m_date = meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting.Meeting_Date else ('无日期' if locale == 'zh_CN' else 'N/A')
        
        if locale == 'zh_CN':
            res = f"我已经为您获取了 **会议 #{meeting.Meeting_Number} ({m_date})** 的官方日程表 —— 如下：\n"
            res += f"📋 **会议 #{meeting.Meeting_Number} 日程表 — {meeting.Meeting_Title or '无主题'}**\n\n"
            res += "| 序号 | 时间 | 环节 | 负责人 |\n"
            res += "|---|------|------|-------|\n"
        else:
            res = f"I went ahead and pulled the official agenda for **Meeting #{meeting.Meeting_Number} ({m_date})** — here it is:\n"
            res += f"📋 **Meeting #{meeting.Meeting_Number} Agenda — {meeting.Meeting_Title or 'No Theme'}**\n\n"
            res += "| # | Time | Item | Owner |\n"
            res += "|---|------|------|-------|\n"
            
        for log in logs:
            time_str = log.Start_Time.strftime('%H:%M') if log.Start_Time else "—"
            
            # Format item/title
            item_title = log.Session_Title.strip() if log.Session_Title else ""
            if not item_title and log.session_type:
                item_title = log.session_type.Title
            if not item_title:
                item_title = "未命名环节" if locale == 'zh_CN' else "Untitled Item"
                
            # If section divider
            is_section = log.session_type and log.session_type.Title == "Section"
            if is_section:
                item_title = f"**{item_title}**"
                
            owner_name = log.owner.Name if log.owner else "—"
            
            res += f"| {log.Meeting_Seq} | {time_str} | {item_title} | {owner_name} |\n"
            
        return {'success': True, 'message': res}

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
            old_status = meeting.status or 'unpublished'
            
            # Enforce linear progression: unpublished -> not started -> running -> finished
            # Cancelled is allowed from any state, and transitioning to the same state is allowed.
            if new_status != 'cancelled' and new_status != old_status:
                allowed = False
                if old_status == 'unpublished' and new_status == 'not started':
                    allowed = True
                elif old_status == 'not started' and new_status == 'running':
                    allowed = True
                elif old_status == 'running' and new_status == 'finished':
                    allowed = True
                    
                if not allowed:
                    return {
                        'success': False, 
                        'message': f"Cannot transition meeting status directly from '{old_status}' to '{new_status}'. Meetings must follow the linear progression: unpublished -> not started -> running -> finished."
                    }
            
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

        from app.translations.translations import get_locale
        locale = get_locale()

        if locale == 'zh_CN':
            status_translation = {
                'unpublished': '未发布',
                'not started': '未开始',
                'running': '进行中',
                'finished': '已结束',
                'cancelled': '已取消'
            }
            status_zh = status_translation.get(meeting.status, meeting.status)
            res = f"会议 **#{meeting.Meeting_Number}** 的投票结果 ({status_zh})：\n"
            if not vote_counts:
                res += "* 暂无投票记录。"
                return {'success': True, 'message': res}
        else:
            res = f"Voting results for **Meeting #{meeting.Meeting_Number}** ({meeting.status}):\n"
            if not vote_counts:
                res += "* No votes have been cast yet."
                return {'success': True, 'message': res}

        for cat, candidates in cat_map.items():
            # Sort candidates by vote count descending
            sorted_candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
            if locale == 'zh_CN':
                cat_zh = {
                    'speaker': '最佳演讲者',
                    'evaluator': '最佳评估者',
                    'table-topic-speaker': '最佳即兴演讲者',
                    'table topics speaker': '最佳即兴演讲者',
                    'role-taker': '最佳角色扮演者',
                    'role taker': '最佳角色扮演者',
                    'debater': '最佳辩手'
                }.get(cat.lower(), cat.capitalize().replace('-', ' '))
                res += f"\n**{cat_zh}**：\n"
                for name, count in sorted_candidates:
                    res += f"* {name}: {count} 票\n"
            else:
                res += f"\n**Best {cat.capitalize().replace('-', ' ')}**:\n"
                for name, count in sorted_candidates:
                    res += f"* {name}: {count} vote(s)\n"

        # Stored winners (for finished meetings)
        if meeting.status == 'finished':
            if locale == 'zh_CN':
                res += "\n🏆 **官方获奖名单**：\n"
            else:
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
                        if locale == 'zh_CN':
                            title_zh = {
                                'Speaker': '最佳演讲者',
                                'Evaluator': '最佳评估者',
                                'Table Topics Speaker': '最佳即兴演讲者',
                                'Role Taker': '最佳角色扮演者'
                            }.get(title, title)
                            res += f"* {title_zh}：**{contact.Name}**\n"
                        else:
                            res += f"* Best {title}: **{contact.Name}**\n"
                        
        return {'success': True, 'message': res}

    @classmethod
    def tool_manage_excomm_officers(cls, params, user, club_id):
        action = params.get('action')
        if not action:
            return {'success': False, 'message': "Action is required ('query_terms', 'query_officers', 'create_term', 'update_officer', 'set_active_term')."}
            
        action = action.strip().lower()
        valid_actions = ['query_terms', 'query_officers', 'create_term', 'update_officer', 'set_active_term']
        if action not in valid_actions:
            return {'success': False, 'message': f"Invalid action '{action}'. Valid actions are: {', '.join(valid_actions)}."}
            
        if action == 'query_terms':
            if not is_authorized(Permissions.ABOUT_CLUB_VIEW):
                return {'success': False, 'message': "You do not have permission to view excomm terms (ABOUT_CLUB_VIEW)."}
                
            club = db.session.get(Club, club_id)
            if not club:
                return {'success': False, 'message': "Club not found."}
                
            excomms = ExComm.query.filter_by(club_id=club_id).order_by(ExComm.start_date.desc(), ExComm.excomm_term.desc()).all()
            if not excomms:
                return {'success': True, 'message': "No ExComm terms have been defined for this club yet."}
                
            msg = f"**ExComm Terms for {club.club_name}**:\n"
            for ec in excomms:
                is_active = (club.current_excomm_id == ec.id)
                active_str = " **(Active Term)**" if is_active else ""
                name_str = f" ({ec.excomm_name})" if ec.excomm_name else ""
                date_str = ""
                if ec.start_date or ec.end_date:
                    s = ec.start_date.strftime('%Y-%m-%d') if ec.start_date else "N/A"
                    e = ec.end_date.strftime('%Y-%m-%d') if ec.end_date else "N/A"
                    date_str = f" [{s} to {e}]"
                msg += f"* **{ec.excomm_term}**{name_str}{date_str}{active_str}\n"
            return {'success': True, 'message': msg}
            
        elif action == 'query_officers':
            if not is_authorized(Permissions.ABOUT_CLUB_VIEW):
                return {'success': False, 'message': "You do not have permission to view excomm officers (ABOUT_CLUB_VIEW)."}
                
            club = db.session.get(Club, club_id)
            if not club:
                return {'success': False, 'message': "Club not found."}
                
            term = params.get('term')
            excomm = None
            if term:
                term = term.strip()
                excomm = ExComm.query.filter_by(club_id=club_id, excomm_term=term).first()
                if not excomm:
                    return {'success': False, 'message': f"ExComm term '{term}' not found."}
            else:
                if club.current_excomm_id:
                    excomm = db.session.get(ExComm, club.current_excomm_id)
                if not excomm:
                    return {'success': True, 'message': "There is no active ExComm team defined for this club. Specify a term or use create_term action to create one."}
            
            # Retrieve active officers for this term
            active_officers = excomm.get_officers()
            term_str = f"Term: {excomm.excomm_term or 'N/A'}"
            if excomm.excomm_name:
                term_str += f" ({excomm.excomm_name})"
            if club.current_excomm_id == excomm.id:
                term_str += " [Active]"
                
            msg = f"**ExComm Officers Roster** — {term_str}:\n"
            standard_roles = ['President', 'VPE', 'VPM', 'VPPR', 'Secretary', 'Treasurer', 'SAA', 'IPP']
            for role in standard_roles:
                contact = active_officers.get(role)
                contact_name = contact.Name if contact else "—"
                msg += f"* **{role}**: {contact_name}\n"
            return {'success': True, 'message': msg}
            
        elif action == 'create_term':
            if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
                return {'success': False, 'message': "You do not have permission to edit excomm settings (ABOUT_CLUB_EDIT)."}
                
            club = db.session.get(Club, club_id)
            if not club:
                return {'success': False, 'message': "Club not found."}
                
            term = params.get('term')
            if not term:
                return {'success': False, 'message': "Term code (e.g. '26H2') is required to create a new term."}
            term = term.strip()
            
            # Check if term already exists
            existing = ExComm.query.filter_by(club_id=club_id, excomm_term=term).first()
            if existing:
                return {'success': False, 'message': f"ExComm term '{term}' already exists for this club."}
                
            term_name = params.get('term_name')
            start_date_str = params.get('start_date')
            end_date_str = params.get('end_date')
            
            start_date = None
            end_date = None
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str.strip(), '%Y-%m-%d').date()
                except ValueError:
                    return {'success': False, 'message': "Invalid start_date format. Use YYYY-MM-DD."}
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str.strip(), '%Y-%m-%d').date()
                except ValueError:
                    return {'success': False, 'message': "Invalid end_date format. Use YYYY-MM-DD."}
                    
            try:
                new_ec = ExComm(
                    club_id=club_id,
                    excomm_term=term,
                    excomm_name=term_name,
                    start_date=start_date,
                    end_date=end_date
                )
                db.session.add(new_ec)
                db.session.commit()
                return {'success': True, 'message': f"Successfully created new ExComm term '{term}'."}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Failed to create term: {str(e)}"}
                
        elif action == 'update_officer':
            if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
                return {'success': False, 'message': "You do not have permission to edit excomm officers (ABOUT_CLUB_EDIT)."}
                
            role_name_raw = params.get('role_name')
            contact_name = params.get('contact_name')
            term = params.get('term')
            
            if not role_name_raw:
                return {'success': False, 'message': "Role name is required for update."}
                
            # Normalize role name
            role_name_norm = role_name_raw.strip().lower()
            role_map = {
                'president': 'President',
                'vpe': 'VPE',
                'vp education': 'VPE',
                'vice president education': 'VPE',
                'education': 'VPE',
                'vpm': 'VPM',
                'vp membership': 'VPM',
                'vice president membership': 'VPM',
                'membership': 'VPM',
                'vppr': 'VPPR',
                'vp public relations': 'VPPR',
                'vice president public relations': 'VPPR',
                'pr': 'VPPR',
                'public relations': 'VPPR',
                'secretary': 'Secretary',
                'treasurer': 'Treasurer',
                'saa': 'SAA',
                'sergeant at arms': 'SAA',
                'sergeant': 'SAA',
                'ipp': 'IPP',
                'immediate past president': 'IPP',
                'past president': 'IPP'
            }
            
            target_role = role_map.get(role_name_norm)
            if not target_role:
                return {'success': False, 'message': f"Invalid officer role '{role_name_raw}'. Valid roles are: President, VPE, VPM, VPPR, Secretary, Treasurer, SAA, IPP."}
                
            club = db.session.get(Club, club_id)
            if not club:
                return {'success': False, 'message': "Club not found."}
                
            excomm = None
            if term:
                term = term.strip()
                excomm = ExComm.query.filter_by(club_id=club_id, excomm_term=term).first()
                if not excomm:
                    return {'success': False, 'message': f"ExComm term '{term}' not found."}
            else:
                if club.current_excomm_id:
                    excomm = db.session.get(ExComm, club.current_excomm_id)
                # If no term specified and no active excomm exists, create one with default term code
                if not excomm:
                    now = datetime.now()
                    default_term = f"{now.year % 100}{'H1' if now.month <= 6 else 'H2'}"
                    excomm = ExComm(
                        club_id=club.id,
                        excomm_term=default_term
                    )
                    db.session.add(excomm)
                    db.session.flush()
                    club.current_excomm_id = excomm.id
            
            # Resolve role MeetingRole from DB
            from app.models import MeetingRole
            role_obj = MeetingRole.query.filter_by(name=target_role).first()
            if not role_obj:
                return {'success': False, 'message': f"MeetingRole '{target_role}' not found in database."}
                
            is_clear = not contact_name or str(contact_name).strip().lower() in ['none', 'clear', 'empty', 'null', '']
            affected_contact_ids = set()
            
            if is_clear:
                officer_entry = ExcommOfficer.query.filter_by(
                    excomm_id=excomm.id,
                    meeting_role_id=role_obj.id
                ).first()
                if officer_entry:
                    affected_contact_ids.add(officer_entry.contact_id)
                    db.session.delete(officer_entry)
                    
                # Sync status in ContactClub if updating the active term
                if club.current_excomm_id == excomm.id and affected_contact_ids:
                    from app.utils import sync_club_officer_status
                    sync_club_officer_status(club_id, list(affected_contact_ids))
                    
                db.session.commit()
                return {'success': True, 'message': f"Successfully cleared the {target_role} officer position for term '{excomm.excomm_term}'."}
                
            else:
                # Find the contact
                contact = cls.resolve_contact(contact_name, club_id)
                if not contact:
                    return {'success': False, 'message': f"Contact '{contact_name}' not found."}
                    
                officer_entry = ExcommOfficer.query.filter_by(
                    excomm_id=excomm.id,
                    meeting_role_id=role_obj.id
                ).first()
                
                if officer_entry:
                    affected_contact_ids.add(officer_entry.contact_id)
                    officer_entry.contact_id = contact.id
                else:
                    new_officer = ExcommOfficer(
                        excomm_id=excomm.id,
                        contact_id=contact.id,
                        meeting_role_id=role_obj.id
                    )
                    db.session.add(new_officer)
                    
                affected_contact_ids.add(contact.id)
                
                # Sync status in ContactClub if updating the active term
                if club.current_excomm_id == excomm.id:
                    from app.utils import sync_club_officer_status
                    sync_club_officer_status(club_id, list(affected_contact_ids))
                    
                db.session.commit()
                return {'success': True, 'message': f"Successfully updated the {target_role} officer to {contact.Name} for term '{excomm.excomm_term}'."}
                
        elif action == 'set_active_term':
            if not is_authorized(Permissions.ABOUT_CLUB_EDIT):
                return {'success': False, 'message': "You do not have permission to edit excomm settings (ABOUT_CLUB_EDIT)."}
                
            club = db.session.get(Club, club_id)
            if not club:
                return {'success': False, 'message': "Club not found."}
                
            term = params.get('term')
            if not term:
                return {'success': False, 'message': "Term code (e.g. '26H2') is required to set it active."}
            term = term.strip()
            
            excomm = ExComm.query.filter_by(club_id=club_id, excomm_term=term).first()
            if not excomm:
                return {'success': False, 'message': f"ExComm term '{term}' not found."}
                
            try:
                club.current_excomm_id = excomm.id
                
                # Sync officer flag for all contacts in the club
                from app.utils import sync_club_officer_status
                sync_club_officer_status(club_id, contact_ids=None)
                
                db.session.commit()
                return {'success': True, 'message': f"Successfully set ExComm term '{term}' as the active term for the club."}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Failed to set active term: {str(e)}"}

    @classmethod
    def tool_query_pathways_library(cls, params, user, club_id):
        pathway_name = params.get('pathway_name')
        level_val = params.get('level')
        project_name = params.get('project_name')

        # 1. Query by specific project name
        if project_name:
            projects = Project.query.filter(Project.Project_Name.ilike(f"%{project_name}%")).all()
            if not projects:
                return {'success': False, 'message': f"No project matching '{project_name}' was found in the library."}
            
            if len(projects) > 1:
                exact_matches = [p for p in projects if p.Project_Name.lower() == project_name.lower()]
                if len(exact_matches) == 1:
                    projects = exact_matches
                else:
                    lines = [f"* **{p.Project_Name}** (ID: {p.id})" for p in projects]
                    return {
                        'success': True,
                        'message': f"Multiple projects matched '{project_name}':\n" + "\n".join(lines) + "\n\nPlease specify the exact project name."
                    }

            proj = projects[0]
            pps = PathwayProject.query.filter_by(project_id=proj.id).all()
            links = []
            for pp in pps:
                p_status = pp.pathway.status if pp.pathway else 'active'
                if p_status == 'active':
                    type_str = pp.type.value if hasattr(pp.type, 'value') else str(pp.type)
                    links.append(f"  - **{pp.pathway.name}** ({pp.pathway.abbr}): Level {pp.level} ({type_str}) [Code: {pp.code}]")
            
            dur_str = f"{proj.Duration_Min}-{proj.Duration_Max} min" if proj.Duration_Min and proj.Duration_Max else "N/A"
            msg = (
                f"📖 **Project Details: {proj.Project_Name}**\n"
                f"* **Format**: {proj.Format or 'N/A'}\n"
                f"* **Duration**: {dur_str}\n"
                f"* **Purpose**: {proj.Purpose or 'N/A'}\n"
                f"* **Overview**: {proj.Overview or 'N/A'}\n"
                f"* **Requirements**: {proj.Requirements or 'N/A'}\n"
            )
            if proj.Introduction:
                msg += f"* **Introduction**: {proj.Introduction}\n"
            if proj.Resources:
                msg += f"* **Resources**: {proj.Resources}\n"
            if links:
                msg += "\n**Pathways & Levels containing this project**:\n" + "\n".join(links)
            else:
                msg += "\nThis project is not linked to any active pathways."
            return {'success': True, 'message': msg}

        # 2. Query by level but without pathway name
        if level_val is not None and not pathway_name:
            all_paths = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
            path_list = [f"* **{p.name}** ({p.abbr})" for p in all_paths]
            return {
                'success': False,
                'message': "Please specify a pathway name to query projects by level. Available pathways:\n" + "\n".join(path_list)
            }

        # 3. Query by pathway name (and optional level)
        if pathway_name:
            pathway = Pathway.query.filter(
                (Pathway.name.ilike(pathway_name)) | (Pathway.abbr.ilike(pathway_name))
            ).first()
            
            if not pathway:
                all_paths = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
                path_list = [f"* **{p.name}** ({p.abbr})" for p in all_paths]
                return {
                    'success': False,
                    'message': f"Pathway '{pathway_name}' not found. Available active pathways:\n" + "\n".join(path_list)
                }

            level = None
            if level_val is not None:
                try:
                    level = int(level_val)
                    if level < 1 or level > 5:
                        raise ValueError()
                except ValueError:
                    return {'success': False, 'message': "Level must be an integer between 1 and 5."}

            if level:
                pps = PathwayProject.query.filter_by(path_id=pathway.id, level=level).order_by(PathwayProject.type, PathwayProject.code).all()
                if not pps:
                    return {'success': True, 'message': f"No projects found under Level {level} of the **{pathway.name}** pathway."}
                
                reqs = []
                electives = []
                others = []
                for pp in pps:
                    p_name = pp.project.Project_Name if pp.project else "Unknown"
                    type_str = pp.type.value if hasattr(pp.type, 'value') else str(pp.type)
                    proj_line = f"* **{p_name}** [Code: {pp.code}]"
                    if type_str == 'required':
                        reqs.append(proj_line)
                    elif type_str == 'elective':
                        electives.append(proj_line)
                    else:
                        others.append(proj_line)
                
                msg = f"🏫 **{pathway.name} ({pathway.abbr}) - Level {level} Projects**\n"
                if reqs:
                    msg += "\n**Required Projects**:\n" + "\n".join(reqs)
                if electives:
                    msg += "\n**Elective Projects**:\n" + "\n".join(electives)
                if others:
                    msg += "\n**Other Projects**:\n" + "\n".join(others)
                return {'success': True, 'message': msg}
            else:
                pps = PathwayProject.query.filter_by(path_id=pathway.id).order_by(PathwayProject.level, PathwayProject.type, PathwayProject.code).all()
                if not pps:
                    return {'success': True, 'message': f"No projects registered for the **{pathway.name}** pathway."}
                
                levels_data = {l: {'required': [], 'elective': [], 'other': []} for l in range(1, 6)}
                for pp in pps:
                    lvl = pp.level
                    if lvl not in levels_data:
                        continue
                    p_name = pp.project.Project_Name if pp.project else "Unknown"
                    type_str = pp.type.value if hasattr(pp.type, 'value') else str(pp.type)
                    levels_data[lvl][type_str].append(f"  - **{p_name}** [Code: {pp.code}]")

                msg = f"🏫 **{pathway.name} ({pathway.abbr}) Pathways Library**\n"
                for lvl in range(1, 6):
                    msg += f"\n**Level {lvl}**\n"
                    reqs = levels_data[lvl]['required']
                    elects = levels_data[lvl]['elective']
                    others = levels_data[lvl]['other']
                    
                    if reqs:
                        msg += "  *Required:\n" + "\n".join(reqs) + "\n"
                    if elects:
                        msg += "  *Elective:\n" + "\n".join(elects) + "\n"
                    if others:
                        msg += "  *Other:\n" + "\n".join(others) + "\n"
                    if not reqs and not elects and not others:
                        msg += "  No projects listed for this level.\n"
                return {'success': True, 'message': msg.strip()}

        # 4. No parameters: list all active pathways
        all_paths = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
        msg = "🏫 **Toastmasters Pathways Library**\n\nActive Pathways:\n"
        for p in all_paths:
            msg += f"* **{p.name}** ({p.abbr}) - {p.type or 'Pathway'}\n"
        msg += "\nTo query a specific pathway, use: `/query-pathways <pathway_name> [level]` or ask me directly."
        return {'success': True, 'message': msg}

    @classmethod
    def tool_manage_waitlist(cls, params, user, club_id):
        from app.models.roster import Waitlist
        from app.models.planner import Planner
        from sqlalchemy import or_

        action = params.get('action')
        if not action:
            return {'success': False, 'message': "Action is required ('query', 'create', 'update', 'remove', 'approve')."}
            
        action = action.strip().lower()
        valid_actions = ['query', 'create', 'update', 'remove', 'approve']
        if action not in valid_actions:
            return {'success': False, 'message': f"Invalid action '{action}'. Valid actions are: {', '.join(valid_actions)}."}
            
        meeting_ident = params.get('meeting_identifier')
        if not meeting_ident:
            return {'success': False, 'message': "Meeting identifier is required."}
            
        meeting = cls.resolve_meeting(meeting_ident, club_id)
        if not meeting:
            return {'success': False, 'message': f"Meeting '{meeting_ident}' not found."}
            
        # Check permissions
        if action == 'query':
            if not is_authorized(Permissions.BOOKING_VIEW_ALL):
                return {'success': False, 'message': "You do not have permission to view role bookings (BOOKING_VIEW_ALL)."}
        elif action == 'approve':
            if not is_authorized(Permissions.BOOKING_ASSIGN_ALL):
                return {'success': False, 'message': "You do not have permission to assign roles or approve waitlists (BOOKING_ASSIGN_ALL)."}
        else: # create, update, remove
            user_contact = user.get_contact(club_id) if user else None
            current_user_contact_id = user_contact.id if user_contact else None
            
            # Resolve target contact first to check if they are self
            contact_name = params.get('contact_name')
            if not contact_name:
                return {'success': False, 'message': "Contact name is required."}
            contact = cls.resolve_contact(contact_name, club_id)
            if not contact:
                return {'success': False, 'message': f"Contact '{contact_name}' not found."}
                
            is_admin = is_authorized(Permissions.BOOKING_ASSIGN_ALL) or is_authorized(Permissions.AGENDA_EDIT)
            is_self = (current_user_contact_id and contact.id == current_user_contact_id)
            
            if not is_admin:
                if not is_self:
                    return {'success': False, 'message': "You do not have permission to manage other contacts' waitlist entries."}
                if not is_authorized(Permissions.BOOKING_BOOK_OWN):
                    return {'success': False, 'message': "You do not have permission to book roles or manage your own waitlist."}
                    
        # Check if meeting is finished (no modifications allowed)
        if action != 'query' and meeting.status == 'finished':
            return {'success': False, 'message': f"Meeting #{meeting.Meeting_Number} has already finished. Waitlist modifications are not allowed."}

        # Resolve role_name for create, update, remove, approve
        log = None
        role_name = params.get('role_name')
        if action != 'query' or role_name:
            if not role_name:
                return {'success': False, 'message': "Role name is required."}
            log = cls.resolve_session_log(meeting.id, role_name, club_id)
            if not log:
                return {'success': False, 'message': f"Role '{role_name}' not found in Meeting #{meeting.Meeting_Number} agenda."}

        # Execute actions
        if action == 'query':
            if log:
                # Query specific role waitlist
                related_session_ids = RoleService._get_related_session_ids(log)
                waitlist_entries = Waitlist.query.filter(Waitlist.session_log_id.in_(related_session_ids)).order_by(Waitlist.timestamp.asc()).all()
            else:
                # Query all waitlists for the meeting
                session_logs = SessionLog.query.filter_by(meeting_id=meeting.id).all()
                session_log_ids = [sl.id for sl in session_logs]
                waitlist_entries = Waitlist.query.filter(Waitlist.session_log_id.in_(session_log_ids)).order_by(Waitlist.session_log_id, Waitlist.timestamp.asc()).all()
                
            if not waitlist_entries:
                role_msg = f" for '{log.session_type.role.name}'" if log else ""
                return {'success': True, 'message': f"No waitlist entries found{role_msg} in Meeting #{meeting.Meeting_Number}."}
                
            msg = f"📋 **Waitlist for Meeting #{meeting.Meeting_Number}**:\n\n"
            msg += "| Role | Name | Joined At | Pathway | Project | Speech Title |\n"
            msg += "|---|---|---|---|---|---|\n"
            
            for entry in waitlist_entries:
                r_name = entry.session_log.session_type.role.name if (entry.session_log and entry.session_log.session_type and entry.session_log.session_type.role) else "Unknown"
                c_name = entry.contact.Name if entry.contact else "Unknown"
                joined_at = entry.timestamp.strftime('%Y-%m-%d %H:%M') if entry.timestamp else "N/A"
                
                # Fetch speech details from Planner if available
                pathway = "—"
                project_title = "—"
                speech_title = "—"
                
                if entry.contact and entry.contact.user_id and entry.session_log and entry.session_log.session_type:
                    role_id = entry.session_log.session_type.role_id
                    plan = Planner.query.filter_by(
                        user_id=entry.contact.user_id,
                        meeting_id=meeting.id,
                        meeting_role_id=role_id
                    ).first()
                    if plan:
                        pathway = plan.pathway if plan.pathway else "—"
                        project_title = plan.project.Project_Name if (plan.project and plan.project.Project_Name) else "—"
                        speech_title = plan.title if plan.title else "—"
                        
                msg += f"| {r_name} | {c_name} | {joined_at} | {pathway} | {project_title} | {speech_title} |\n"
                
            return {'success': True, 'message': msg}
            
        elif action == 'create':
            # Resolve pathway & project if provided
            pathway_name = params.get('pathway_name')
            pathway = None
            if pathway_name:
                pathway = Pathway.query.filter(
                    or_(Pathway.name.ilike(pathway_name), Pathway.abbr.ilike(pathway_name))
                ).first()
                if not pathway:
                    return {'success': False, 'message': f"Pathway '{pathway_name}' not found."}
                    
            project_name = params.get('project_name')
            project = None
            if project_name:
                projects = Project.query.filter(Project.Project_Name.ilike(f"%{project_name}%")).all()
                if not projects:
                    return {'success': False, 'message': f"Project '{project_name}' not found."}
                if len(projects) > 1:
                    exact_matches = [p for p in projects if p.Project_Name.lower() == project_name.lower()]
                    if len(exact_matches) == 1:
                        project = exact_matches[0]
                    else:
                        lines = [f"* {p.Project_Name}" for p in projects]
                        return {'success': False, 'message': f"Multiple projects matched '{project_name}':\n" + "\n".join(lines) + "\n\nPlease specify the exact project name."}
                else:
                    project = projects[0]
                    
            speech_title = params.get('speech_title')
            
            try:
                success, msg = RoleService.join_waitlist(
                    log,
                    contact.id,
                    project_id=project.id if project else None,
                    title=speech_title,
                    pathway=pathway.name if pathway else None
                )
                if success:
                    db.session.commit()
                    return {'success': True, 'message': f"Successfully added {contact.Name} to the waitlist for {log.session_type.role.name}."}
                else:
                    return {'success': False, 'message': f"Failed to add to waitlist: {msg}"}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Error during join waitlist: {str(e)}"}
                
        elif action == 'update':
            # Check if user is waitlisted
            waitlist_entry = Waitlist.query.filter_by(session_log_id=log.id, contact_id=contact.id).first()
            if not waitlist_entry:
                return {'success': False, 'message': f"{contact.Name} is not on the waitlist for {log.session_type.role.name}."}
                
            role_id = log.session_type.role_id if log.session_type else None
            if not role_id:
                return {'success': False, 'message': "Cannot determine role ID."}
                
            # Resolve pathway & project if provided
            pathway_name = params.get('pathway_name')
            pathway = None
            if pathway_name:
                pathway = Pathway.query.filter(
                    or_(Pathway.name.ilike(pathway_name), Pathway.abbr.ilike(pathway_name))
                ).first()
                if not pathway:
                    return {'success': False, 'message': f"Pathway '{pathway_name}' not found."}
                    
            project_name = params.get('project_name')
            project = None
            if project_name:
                projects = Project.query.filter(Project.Project_Name.ilike(f"%{project_name}%")).all()
                if not projects:
                    return {'success': False, 'message': f"Project '{project_name}' not found."}
                if len(projects) > 1:
                    exact_matches = [p for p in projects if p.Project_Name.lower() == project_name.lower()]
                    if len(exact_matches) == 1:
                        project = exact_matches[0]
                    else:
                        lines = [f"* {p.Project_Name}" for p in projects]
                        return {'success': False, 'message': f"Multiple projects matched '{project_name}':\n" + "\n".join(lines) + "\n\nPlease specify the exact project name."}
                else:
                    project = projects[0]
                    
            speech_title = params.get('speech_title')
            
            # Find/create planner details
            plan = Planner.query.filter_by(
                user_id=contact.user_id,
                meeting_id=meeting.id,
                meeting_role_id=role_id
            ).first()
            
            if not plan:
                plan = Planner(
                    user_id=contact.user_id,
                    meeting_id=meeting.id,
                    meeting_role_id=role_id,
                    club_id=club_id
                )
                db.session.add(plan)
                
            if pathway:
                plan.pathway = pathway.name
            if project:
                plan.project_id = project.id
            if speech_title is not None:
                plan.title = speech_title
                
            plan.status = 'waitlist'
            
            try:
                db.session.commit()
                RoleService._clear_meeting_cache(meeting.id)
                RoleService.sync_planner_statuses(meeting.id, role_id)
                return {'success': True, 'message': f"Successfully updated waitlist preferences for {contact.Name}."}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Failed to update waitlist preferences: {str(e)}"}
                
        elif action == 'remove':
            try:
                success, msg = RoleService.leave_waitlist(log, contact.id)
                if success:
                    db.session.commit()
                    return {'success': True, 'message': f"Successfully removed {contact.Name} from the waitlist."}
                else:
                    return {'success': False, 'message': f"Failed to remove from waitlist: {msg}"}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Error during remove waitlist: {str(e)}"}
                
        elif action == 'approve':
            try:
                success, msg = RoleService.approve_waitlist(log)
                if success:
                    db.session.commit()
                    return {'success': True, 'message': f"Successfully approved next user in waitlist for {log.session_type.role.name}."}
                else:
                    return {'success': False, 'message': f"Failed to approve waitlist: {msg}"}
            except Exception as e:
                db.session.rollback()
                return {'success': False, 'message': f"Error during waitlist approval: {str(e)}"}
