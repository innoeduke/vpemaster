import shlex
from app.services.chat_tool_executor import ChatToolExecutor

class CommandParser:
    """
    Parses structured commands starting with '/' and routes them to ChatToolExecutor.
    Maintains a strict CLI-like structure without calling external LLMs.
    """

    @staticmethod
    def parse_and_execute(message_text, user, club_id):
        """
        Parses text and executes the corresponding tool action.
        Returns a tuple: (success_bool, response_message)
        """
        text = str(message_text).strip()
        if not text.startswith('/'):
            # Prompt user to use /help
            return False, "Invalid command format. Type `/help` to see the list of available commands."

        try:
            # Parse tokens using shlex to support quotes: /assign 350 "Ah Counter" "Kyle Wei"
            tokens = shlex.split(text)
        except ValueError as e:
            return False, f"Parsing error: {str(e)}. Make sure your quotes are closed properly."

        if not tokens:
            return False, "Empty command."

        cmd = tokens[0].lower()
        args = tokens[1:]

        if cmd == '/help':
            return True, CommandParser.get_help_text(user, club_id)

        # Route commands to tool parameters
        if cmd == '/create-meeting':
            if len(args) < 1:
                from app.models import Meeting
                type_to_template = Meeting.get_type_to_template(club_id)
                template_list = ", ".join([f"'{k}'" for k in type_to_template.keys()])
                return False, (
                    "Usage: `/create-meeting <date> [template_name]`\n"
                    f"Available templates: {template_list}\n"
                    "Example: `/create-meeting 2026-06-15 \"Keynote Speech\"`"
                )
            params = {'date': args[0]}
            if len(args) >= 2:
                params['template_name'] = args[1]
            res = ChatToolExecutor.execute('create_meeting', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/assign':
            if len(args) < 2:
                return False, (
                    "Usage:\n"
                    "  - Query assignment: `/assign <meeting_number> <role_name>`\n"
                    "  - Assign role: `/assign <meeting_number> <role_name> <contact_name>`\n"
                    "Example: `/assign 350 \"Ah Counter\" \"Kyle Wei\"`"
                )
            
            if len(args) == 2:
                meeting = ChatToolExecutor.resolve_meeting(args[0], club_id)
                if not meeting:
                    return False, f"Meeting '{args[0]}' not found."
                log = ChatToolExecutor.resolve_session_log(meeting.id, args[1], club_id)
                if not log:
                    return False, f"Role '{args[1]}' not found in Meeting #{meeting.Meeting_Number} agenda."
                role_name = log.session_type.role.name
                if log.owner:
                    return True, f"Role '{role_name}' in Meeting #{meeting.Meeting_Number} is currently assigned to {log.owner.Name}."
                else:
                    return True, f"Role '{role_name}' in Meeting #{meeting.Meeting_Number} is currently vacant."
            
            params = {
                'meeting_identifier': args[0],
                'role_name': args[1],
                'contact_name': args[2]
            }
            res = ChatToolExecutor.execute('assign_role', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/cancel-role':
            if len(args) < 2:
                return False, (
                    "Usage:\n"
                    "  - Query assignment: `/cancel-role <meeting_number> <role_name>`\n"
                    "  - Cancel assignment: `/cancel-role <meeting_number> <role_name> <contact_name>`\n"
                    "Example: `/cancel-role 350 \"Ah Counter\" \"Kyle Wei\"`"
                )
            
            if len(args) == 2:
                meeting = ChatToolExecutor.resolve_meeting(args[0], club_id)
                if not meeting:
                    return False, f"Meeting '{args[0]}' not found."
                log = ChatToolExecutor.resolve_session_log(meeting.id, args[1], club_id)
                if not log:
                    return False, f"Role '{args[1]}' not found in Meeting #{meeting.Meeting_Number} agenda."
                role_name = log.session_type.role.name
                if log.owner:
                    return True, f"Role '{role_name}' in Meeting #{meeting.Meeting_Number} is currently assigned to {log.owner.Name}."
                else:
                    return True, f"Role '{role_name}' in Meeting #{meeting.Meeting_Number} is currently vacant."
            
            params = {
                'meeting_identifier': args[0],
                'role_name': args[1],
                'contact_name': args[2]
            }
            res = ChatToolExecutor.execute('cancel_role', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/add-contact':
            if len(args) < 1:
                return False, "Usage: `/add-contact <name> [email] [phone]`\nExample: `/add-contact \"John Smith\" john@example.com 13800000000`"
            params = {'name': args[0]}
            if len(args) >= 2:
                params['email'] = args[1]
            if len(args) >= 3:
                params['phone'] = args[2]
            res = ChatToolExecutor.execute('add_contact', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/check-in':
            if len(args) < 1:
                from app.models.ticket import Ticket
                tickets = Ticket.get_all_for_club(club_id)
                seen = set()
                ticket_names = []
                for t in tickets:
                    if t.name not in seen:
                        seen.add(t.name)
                        ticket_names.append(f"'{t.name}'")
                ticket_list = ", ".join(ticket_names)
                return False, (
                    "Usage:\n"
                    "  - Query check-ins: `/check-in <meeting_number>`\n"
                    "  - Check in participant: `/check-in <meeting_number> <contact_name> [ticket_type]`\n"
                    f"Available ticket types: {ticket_list}\n"
                    "Example: `/check-in 350 \"Kyle Wei\" Officer`"
                )
            
            if len(args) == 1:
                meeting = ChatToolExecutor.resolve_meeting(args[0], club_id)
                if not meeting:
                    return False, f"Meeting '{args[0]}' not found."
                from app.models import Roster
                entries = Roster.query.filter(
                    Roster.meeting_id == meeting.id,
                    Roster.check_in_time.isnot(None)
                ).all()
                if not entries:
                    return True, f"No participants have checked in for Meeting #{meeting.Meeting_Number} yet."
                names = [e.contact.Name for e in entries if e.contact]
                return True, f"Checked-in participants for Meeting #{meeting.Meeting_Number} ({len(names)} total):\n" + "\n".join(f"* {name}" for name in names)
            
            params = {
                'meeting_identifier': args[0],
                'contact_name': args[1]
            }
            if len(args) >= 3:
                params['ticket_type'] = args[2]
            res = ChatToolExecutor.execute('check_in', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/complete-level':
            if len(args) < 2:
                return False, (
                    "Usage:\n"
                    "  - Query completed levels: `/complete-level <contact_name> <pathway_name>`\n"
                    "  - Record completion: `/complete-level <contact_name> <pathway_name> <level>`\n"
                    "Example: `/complete-level \"Kyle Wei\" \"Dynamic Leadership\" 3`"
                )
            
            if len(args) == 2:
                contact = ChatToolExecutor.resolve_contact(args[0], club_id)
                if not contact:
                    return False, f"Contact '{args[0]}' not found."
                from app.models import Pathway, Achievement
                from sqlalchemy import or_
                pathway = Pathway.query.filter(
                    or_(Pathway.name.ilike(args[1]), Pathway.abbr.ilike(args[1]))
                ).first()
                if not pathway:
                    return False, f"Pathway '{args[1]}' not found in pathway library."
                
                contact_user_id = contact.user_id
                if not contact_user_id:
                    from app.models import UserClub
                    user_club = UserClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
                    if user_club:
                        contact_user_id = user_club.user_id
                
                completed = []
                if contact_user_id:
                    achievements = Achievement.query.filter_by(
                        user_id=contact_user_id,
                        achievement_type='level-completion',
                        path_name=pathway.name
                    ).order_by(Achievement.level).all()
                    completed = [a.level for a in achievements]
                
                if completed:
                    levels_str = ", ".join(f"Level {lvl}" for lvl in completed)
                    return True, f"{contact.Name} has completed {levels_str} of '{pathway.name}'."
                else:
                    return True, f"{contact.Name} has not completed any levels in '{pathway.name}' yet."
            
            params = {
                'contact_name': args[0],
                'pathway_name': args[1],
                'level': args[2]
            }
            res = ChatToolExecutor.execute('complete_level', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/pathway-status':
            if len(args) < 1:
                return False, "Usage: `/pathway-status <contact_name>`\nExample: `/pathway-status \"Kyle Wei\"`"
            params = {'contact_name': args[0]}
            res = ChatToolExecutor.execute('get_pathway_status', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/search':
            if len(args) < 1:
                return False, "Usage: `/search <contact_name>`\nExample: `/search \"Kyle\"`"
            params = {'name': args[0]}
            res = ChatToolExecutor.execute('search_contacts', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/meeting-info':
            if len(args) < 1:
                return False, "Usage: `/meeting-info <meeting_number>`\nExample: `/meeting-info 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_meeting_info', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/list-meetings':
            params = {}
            if len(args) >= 1:
                params['status'] = args[0]
            if len(args) >= 2:
                params['limit'] = args[1]
            res = ChatToolExecutor.execute('list_meetings', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/roles':
            if len(args) < 1:
                return False, "Usage: `/roles <meeting_number>`\nExample: `/roles 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_role_assignments', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/available-roles':
            if len(args) < 1:
                return False, "Usage: `/available-roles <meeting_number>`\nExample: `/available-roles 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_available_roles', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/status':
            if len(args) < 1:
                return False, (
                    "Usage:\n"
                    "  - Query status: `/status <meeting_number>`\n"
                    "  - Update status: `/status <meeting_number> <new_status>`\n"
                    "Available statuses: 'unpublished', 'not started', 'running', 'finished', 'cancelled'\n"
                    "Example: `/status 350 running`"
                )
            
            if len(args) == 1:
                meeting = ChatToolExecutor.resolve_meeting(args[0], club_id)
                if not meeting:
                    return False, f"Meeting '{args[0]}' not found."
                return True, f"Meeting #{meeting.Meeting_Number} status is `{meeting.status}`."
            
            params = {
                'meeting_identifier': args[0],
                'status': args[1]
            }
            res = ChatToolExecutor.execute('update_meeting_status', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/voting-results':
            if len(args) < 1:
                return False, "Usage: `/voting-results <meeting_number>`\nExample: `/voting-results 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_voting_results', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/query-pathways':
            params = {}
            if len(args) >= 2 and args[0] in ('--project', '--proj', '-p'):
                params['project_name'] = args[1]
            elif len(args) == 1 and args[0].startswith('--project='):
                params['project_name'] = args[0].split('=', 1)[1]
            else:
                if len(args) >= 1:
                    params['pathway_name'] = args[0]
                if len(args) >= 2:
                    params['level'] = args[1]
            res = ChatToolExecutor.execute('query_pathways_library', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/waitlist':
            if len(args) < 2:
                return False, (
                    "Usage: `/waitlist <action> <meeting_number> [args...]`\n"
                    "Actions:\n"
                    "  - `query`: `/waitlist query <meeting_number> [role_name]`\n"
                    "  - `join`: `/waitlist join <meeting_number> <role_name> <contact_name> [pathway_name] [project_name] [speech_title]`\n"
                    "  - `update`: `/waitlist update <meeting_number> <role_name> <contact_name> [pathway_name] [project_name] [speech_title]`\n"
                    "  - `remove`: `/waitlist remove <meeting_number> <role_name> <contact_name>`\n"
                    "  - `approve`: `/waitlist approve <meeting_number> <role_name>`"
                )
            
            action = args[0].lower()
            meeting_ident = args[1]
            params = {
                'action': action,
                'meeting_identifier': meeting_ident
            }
            
            if action == 'query':
                if len(args) >= 3:
                    params['role_name'] = args[2]
            elif action == 'approve':
                if len(args) < 3:
                    return False, "Usage: `/waitlist approve <meeting_number> <role_name>`"
                params['role_name'] = args[2]
            elif action in ('join', 'create'):
                params['action'] = 'create'
                if len(args) < 4:
                    return False, "Usage: `/waitlist join <meeting_number> <role_name> <contact_name> [pathway_name] [project_name] [speech_title]`"
                params['role_name'] = args[2]
                params['contact_name'] = args[3]
                if len(args) >= 5:
                    params['pathway_name'] = args[4]
                if len(args) >= 6:
                    params['project_name'] = args[5]
                if len(args) >= 7:
                    params['speech_title'] = args[6]
            elif action == 'update':
                if len(args) < 4:
                    return False, "Usage: `/waitlist update <meeting_number> <role_name> <contact_name> [pathway_name] [project_name] [speech_title]`"
                params['role_name'] = args[2]
                params['contact_name'] = args[3]
                if len(args) >= 5:
                    params['pathway_name'] = args[4]
                if len(args) >= 6:
                    params['project_name'] = args[5]
                if len(args) >= 7:
                    params['speech_title'] = args[6]
            elif action in ('remove', 'leave'):
                params['action'] = 'remove'
                if len(args) < 4:
                    return False, "Usage: `/waitlist remove <meeting_number> <role_name> <contact_name>`"
                params['role_name'] = args[2]
                params['contact_name'] = args[3]
            else:
                return False, f"Invalid waitlist action '{action}'. Valid actions are query, join, update, remove, approve."
                
            res = ChatToolExecutor.execute('manage_waitlist', params, user, club_id)
            return res['success'], res['message']

        return False, f"Unknown command '{cmd}'. Type `/help` to see available commands."

    @staticmethod
    def get_help_text(user=None, club_id=None):
        from app.auth.permissions import Permissions

        def check_perm(permission_name):
            if not user:
                return False
            if club_id and hasattr(user, 'has_club_permission'):
                return user.has_club_permission(permission_name, club_id)
            if hasattr(user, 'has_permission'):
                return user.has_permission(permission_name)
            return False

        commands = []

        # Check /create-meeting
        if check_perm(Permissions.MEETING_CREATE):
            try:
                from app.models import Meeting
                type_to_template = Meeting.get_type_to_template(club_id)
                template_list = ", ".join([f"'{k}'" for k in type_to_template.keys()])
                tpl_suffix = f" (Available templates: {template_list})"
            except Exception:
                tpl_suffix = ""
            commands.append(f"* **/create-meeting** `<date>` `[template]` - Create meeting.{tpl_suffix} Example: `/create-meeting 2026-06-15 \"Keynote Speech\"`\n")

        # Check /assign
        if check_perm(Permissions.MEETING_MANAGE):
            commands.append("* **/assign** `<meeting_number>` `<role_name>` `[contact_name]` - Assign role, or query assignee if name omitted. Example: `/assign 350 \"Ah Counter\" \"Kyle Wei\"`\n")

        # Check /cancel-role
        if check_perm(Permissions.MEETING_MANAGE):
            commands.append("* **/cancel-role** `<meeting_number>` `<role_name>` `[contact_name]` - Cancel assignment, or query assignee if name omitted. Example: `/cancel-role 350 \"Ah Counter\" \"Kyle Wei\"`\n")

        # Check /add-contact
        if check_perm(Permissions.ROSTER_EDIT):
            commands.append("* **/add-contact** `<name>` `[email]` `[phone]` - Add guest contact. Example: `/add-contact \"John Smith\"`\n")

        # Check /check-in
        if check_perm(Permissions.ROSTER_EDIT):
            try:
                from app.models import Ticket
                tickets = Ticket.get_all_for_club(club_id)
                seen = set()
                ticket_names = []
                for t in tickets:
                    if t.name not in seen:
                        seen.add(t.name)
                        ticket_names.append(f"'{t.name}'")
                ticket_list = ", ".join(ticket_names)
                tkt_suffix = f" (Available ticket types: {ticket_list})"
            except Exception:
                tkt_suffix = ""
            commands.append(f"* **/check-in** `<meeting_number>` `[contact_name]` `[ticket_type]` - Check in participant, or query check-ins if name omitted.{tkt_suffix} Example: `/check-in 350 \"Kyle Wei\"`\n")

        # Check /complete-level
        if check_perm(Permissions.SPEECH_LOGS_MANAGE):
            commands.append("* **/complete-level** `<contact_name>` `<pathway_name>` `[level]` - Record achievement, or query completed levels if level omitted. Example: `/complete-level \"Kyle Wei\" \"Dynamic Leadership\" 3`\n")

        # Check /pathway-status
        if check_perm(Permissions.LIBRARY_VIEW):
            commands.append("* **/pathway-status** `<contact_name>` - Show pathway progress. Example: `/pathway-status \"Kyle Wei\"`\n")

        # Check /search
        commands.append("* **/search** `<name_query>` - Search contacts. Example: `/search Kyle`\n")

        # Check /meeting-info
        if check_perm(Permissions.MEETING_VIEW_PUBLISHED):
            commands.append("* **/meeting-info** `<meeting_number>` - Get meeting summary. Example: `/meeting-info 350`\n")

        # Check /list-meetings
        if check_perm(Permissions.MEETING_VIEW_PUBLISHED):
            commands.append("* **/list-meetings** `[status]` `[limit]` - List recent/upcoming. (Available statuses: 'unpublished', 'not started', 'running', 'finished', 'cancelled') Example: `/list-meetings running 5`\n")

        # Check /roles
        if check_perm(Permissions.MEETING_VIEW_PUBLISHED):
            commands.append("* **/roles** `<meeting_number>` - Show assigned roles. Example: `/roles 350`\n")

        # Check /available-roles
        if check_perm(Permissions.MEETING_VIEW_PUBLISHED):
            commands.append("* **/available-roles** `<meeting_number>` - Show open roles. Example: `/available-roles 350`\n")

        # Check /status
        if check_perm(Permissions.MEETING_MANAGE):
            commands.append("* **/status** `<meeting_number>` `[new_status]` - Change meeting status, or query status if new status omitted. (Available statuses: 'unpublished', 'not started', 'running', 'finished', 'cancelled') Example: `/status 350 running`\n")

        # Check /voting-results
        if check_perm(Permissions.VOTING_VIEW_RESULTS) or check_perm(Permissions.VOTING_TRACK_PROGRESS):
            commands.append("* **/voting-results** `<meeting_number>` - View best award voting results. Example: `/voting-results 350`\n")

        # Check /query-pathways
        commands.append("* **/query-pathways** `[pathway_name]` `[level]` `[--project name]` - Query pathways and projects library. Example: `/query-pathways PM 3` or `/query-pathways --project \"Ice Breaker\"`\n")
        
        # Check /waitlist
        if check_perm(Permissions.MEETING_VIEW_PUBLISHED):
            commands.append("* **/waitlist** `<action> <meeting_number> [args...]` - Manage waitlists (actions: query, join, update, remove, approve).\n")

        # Check /help
        commands.append("* **/help** - Show this menu.")

        return (
            "💡 **Available Chat Commands (Terminal Mode)**:\n\n" +
            "".join(commands)
        )
