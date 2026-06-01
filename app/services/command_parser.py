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
            return True, CommandParser.get_help_text()

        # Route commands to tool parameters
        if cmd == '/create-meeting':
            if len(args) < 1:
                return False, "Usage: `/create-meeting <date> [template_name]`\nExample: `/create-meeting 2026-06-15 \"Keynote Speech\"`"
            params = {'date': args[0]}
            if len(args) >= 2:
                params['template_name'] = args[1]
            res = ChatToolExecutor.execute('create_meeting', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/assign':
            if len(args) < 3:
                return False, "Usage: `/assign <meeting_id> <role_name> <contact_name>`\nExample: `/assign 350 \"Ah Counter\" \"Kyle Wei\"`"
            params = {
                'meeting_identifier': args[0],
                'role_name': args[1],
                'contact_name': args[2]
            }
            res = ChatToolExecutor.execute('assign_role', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/cancel-role':
            if len(args) < 3:
                return False, "Usage: `/cancel-role <meeting_id> <role_name> <contact_name>`\nExample: `/cancel-role 350 \"Ah Counter\" \"Kyle Wei\"`"
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
            if len(args) < 2:
                return False, "Usage: `/check-in <meeting_id> <contact_name> [ticket_type]`\nExample: `/check-in 350 \"Kyle Wei\" Officer`"
            params = {
                'meeting_identifier': args[0],
                'contact_name': args[1]
            }
            if len(args) >= 3:
                params['ticket_type'] = args[2]
            res = ChatToolExecutor.execute('check_in', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/complete-level':
            if len(args) < 3:
                return False, "Usage: `/complete-level <contact_name> <pathway_name> <level>`\nExample: `/complete-level \"Kyle Wei\" \"Dynamic Leadership\" 3`"
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
                return False, "Usage: `/meeting-info <meeting_id>`\nExample: `/meeting-info 350`"
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
                return False, "Usage: `/roles <meeting_id>`\nExample: `/roles 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_role_assignments', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/available-roles':
            if len(args) < 1:
                return False, "Usage: `/available-roles <meeting_id>`\nExample: `/available-roles 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_available_roles', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/status':
            if len(args) < 2:
                return False, "Usage: `/status <meeting_id> <new_status>`\nExample: `/status 350 running`"
            params = {
                'meeting_identifier': args[0],
                'status': args[1]
            }
            res = ChatToolExecutor.execute('update_meeting_status', params, user, club_id)
            return res['success'], res['message']

        elif cmd == '/voting-results':
            if len(args) < 1:
                return False, "Usage: `/voting-results <meeting_id>`\nExample: `/voting-results 350`"
            params = {'meeting_identifier': args[0]}
            res = ChatToolExecutor.execute('get_voting_results', params, user, club_id)
            return res['success'], res['message']

        return False, f"Unknown command '{cmd}'. Type `/help` to see available commands."

    @staticmethod
    def get_help_text():
        return (
            "💡 **Available Chat Commands (Terminal Mode)**:\n\n"
            "* **/create-meeting** `<date>` `[template]` - Create meeting. Example: `/create-meeting 2026-06-15 \"Keynote Speech\"`\n"
            "* **/assign** `<meeting_id>` `<role_name>` `<contact_name>` - Assign a role. Example: `/assign 350 \"Ah Counter\" \"Kyle Wei\"`\n"
            "* **/cancel-role** `<meeting_id>` `<role_name>` `<contact_name>` - Cancel role assignment. Example: `/cancel-role 350 \"Ah Counter\" \"Kyle Wei\"`\n"
            "* **/add-contact** `<name>` `[email]` `[phone]` - Add guest contact. Example: `/add-contact \"John Smith\"`\n"
            "* **/check-in** `<meeting_id>` `<contact_name>` `[ticket_type]` - Check in participant. Example: `/check-in 350 \"Kyle Wei\"`\n"
            "* **/complete-level** `<contact_name>` `<pathway_name>` `<level>` - Record achievement. Example: `/complete-level \"Kyle Wei\" \"Dynamic Leadership\" 3`\n"
            "* **/pathway-status** `<contact_name>` - Show pathway progress. Example: `/pathway-status \"Kyle Wei\"`\n"
            "* **/search** `<name_query>` - Search contacts. Example: `/search Kyle`\n"
            "* **/meeting-info** `<meeting_id>` - Get meeting summary. Example: `/meeting-info 350`\n"
            "* **/list-meetings** `[status]` `[limit]` - List recent/upcoming. Example: `/list-meetings running 5`\n"
            "* **/roles** `<meeting_id>` - Show assigned roles. Example: `/roles 350`\n"
            "* **/available-roles** `<meeting_id>` - Show open roles. Example: `/available-roles 350`\n"
            "* **/status** `<meeting_id>` `<new_status>` - Change meeting status. Example: `/status 350 running`\n"
            "* **/voting-results** `<meeting_id>` - View best award voting results. Example: `/voting-results 350`\n"
            "* **/help** - Show this menu."
        )
