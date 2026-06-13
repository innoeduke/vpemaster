import json
from datetime import datetime
import anthropic
from flask import current_app
from app import db
from app.services.chat_tool_executor import ChatToolExecutor
from app.models import ChatMessage, Club, Contact

# Anthropic-formatted tool schemas for MiniMax M3
CHAT_TOOLS = [
    {
        "name": "create_meeting",
        "description": "Create a new club meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The date of the meeting in YYYY-MM-DD format."
                },
                "template_name": {
                    "type": "string",
                    "description": "Optional name of the meeting template CSV (e.g. 'Keynote Speech', 'Speech Marathon')."
                }
            },
            "required": ["date"]
        }
    },
    {
        "name": "manage_meeting_roles",
        "description": "Query or manage role bookings and assignments for a meeting (assign, cancel/unassign, list assignments, list available slots).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform: 'assign' (assign contact to role), 'cancel' (cancel contact's role assignment), 'query' (list all current assignments), 'query_available' (list all vacant/unassigned roles)."
                },
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number (e.g. '350') or meeting date (YYYY-MM-DD). Required for all actions."
                },
                "role_name": {
                    "type": "string",
                    "description": "Name of the role (e.g. 'Ah Counter', 'Prepared Speaker', 'Individual Evaluator'). Required for 'assign' and 'cancel'."
                },
                "contact_name": {
                    "type": "string",
                    "description": "The full name of the contact being assigned or cancelled. Required for 'assign' and 'cancel'."
                },
                "speaker_name": {
                    "type": "string",
                    "description": "Optional target name. For roles tied to a specific speaker, speech, or session (e.g. 'Individual Evaluator' evaluating a specific Prepared Speaker, or 'Topics Speaker' under a specific Topicsmaster), specify the name of that speaker, topicsmaster, or moderator."
                }
            },
            "required": ["action", "meeting_identifier"]
        }
    },
    {
        "name": "add_contact",
        "description": "Add a new guest contact profile to the club database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The full name of the new contact."
                },
                "email": {
                    "type": "string",
                    "description": "Optional email address."
                },
                "phone": {
                    "type": "string",
                    "description": "Optional phone number."
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "check_in",
        "description": "Check in a contact on the meeting attendance roster.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                },
                "contact_name": {
                    "type": "string",
                    "description": "Name of the person checking in."
                },
                "ticket_type": {
                    "type": "string",
                    "description": "Optional ticket type ('Officer', 'Early-bird', 'Walk-in')."
                }
            },
            "required": ["meeting_identifier", "contact_name"]
        }
    },
    {
        "name": "complete_level",
        "description": "Record a level completion achievement for a member.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {
                    "type": "string",
                    "description": "Name of the member."
                },
                "pathway_name": {
                    "type": "string",
                    "description": "Name of the pathway (e.g. 'Dynamic Leadership')."
                },
                "level": {
                    "type": "integer",
                    "description": "Level number completed (1-5)."
                },
                "award_date": {
                    "type": "string",
                    "description": "Optional date in YYYY-MM-DD format."
                }
            },
            "required": ["contact_name", "pathway_name", "level"]
        }
    },
    {
        "name": "get_pathway_status",
        "description": "Get a contact's current Toastmasters pathway progress and achievements. You MUST call this tool to retrieve pathway status. Do not guess or invent progress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contact_name": {
                    "type": "string",
                    "description": "The name of the contact."
                }
            },
            "required": ["contact_name"]
        }
    },
    {
        "name": "search_contacts",
        "description": "Search for contacts in the club database by name query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name query substring."
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_meeting_info",
        "description": "Get details of a specific meeting (title, date, manager, WOD, etc.). You MUST call this tool to retrieve meeting details. Do not guess or invent info.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                }
            },
            "required": ["meeting_identifier"]
        }
    },
    {
        "name": "list_meetings",
        "description": "List meetings matching criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status: 'unpublished', 'not started', 'running', 'finished', 'cancelled'."
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of meetings to return (default 5)."
                }
            }
        }
    },

    {
        "name": "update_meeting_status",
        "description": "Change the operational status of a meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                },
                "status": {
                    "type": "string",
                    "description": "New status: 'unpublished', 'not started', 'running', 'finished', 'cancelled'."
                }
            },
            "required": ["meeting_identifier", "status"]
        }
    },
    {
        "name": "get_voting_results",
        "description": "Get voting tallies and winners for a specific meeting. You MUST call this tool to retrieve voting results. Do not guess or invent winners.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                }
            },
            "required": ["meeting_identifier"]
        }
    },
    {
        "name": "get_meeting_agenda",
        "description": "Get the detailed agenda items (sequence of events, timings, titles, and owners) for a specific meeting. You MUST call this tool when the user asks for agenda items or meeting agenda.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                }
            },
            "required": ["meeting_identifier"]
        }
    },
    {
        "name": "manage_excomm_officers",
        "description": "Query or manage the club's ExComm (Executive Committee) terms and officer rosters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform: 'query_terms' (list all terms), 'query_officers' (list roster for a term), 'create_term' (add new term), 'update_officer' (assign/clear officer for a term), 'set_active_term' (make a term active)."
                },
                "term": {
                    "type": "string",
                    "description": "The excomm term code (e.g. '26H1', '26H2'). Used/optional in query_officers, create_term, update_officer, set_active_term. Defaults to current active term if omitted."
                },
                "term_name": {
                    "type": "string",
                    "description": "Optional name for a term (e.g. 'Memory Makers'). Used in create_term."
                },
                "start_date": {
                    "type": "string",
                    "description": "Optional term start date in YYYY-MM-DD format. Used in create_term."
                },
                "end_date": {
                    "type": "string",
                    "description": "Optional term end date in YYYY-MM-DD format. Used in create_term."
                },
                "role_name": {
                    "type": "string",
                    "description": "Used in update_officer. The officer role name: 'President', 'VPE', 'VPM', 'VPPR', 'Secretary', 'Treasurer', 'SAA', or 'Immediate Past President'."
                },
                "contact_name": {
                    "type": "string",
                    "description": "Used in update_officer. The name of the member contact to assign. To clear/remove the assignment, pass 'none' or leave it empty."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "query_pathways_library",
        "description": "Query details of pathways, levels, and specific projects from the Toastmasters pathways library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pathway_name": {
                    "type": "string",
                    "description": "Optional name or abbreviation of the pathway (e.g. 'Presentation Mastery' or 'PM')."
                },
                "level": {
                    "type": "integer",
                    "description": "Optional level number (1 to 5) to filter projects."
                },
                "project_name": {
                    "type": "string",
                    "description": "Optional specific project name (e.g. 'Ice Breaker') to query its full details."
                }
            }
        }
    },
    {
        "name": "manage_waitlist",
        "description": "Query or manage the waitlist for meeting roles (join waitlist, leave/remove from waitlist, update speech/project details on waitlist, query waitlist, approve/promote from waitlist).",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform: 'query' (list waitlist entries), 'create' (add contact to waitlist), 'update' (update waitlisted speech/project details), 'remove' (remove contact from waitlist), 'approve' (promote next waitlisted person to role owner)."
                },
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number (e.g. '350') or meeting date (YYYY-MM-DD). Required for all actions."
                },
                "role_name": {
                    "type": "string",
                    "description": "The name of the meeting role (e.g. 'Prepared Speaker', 'Ah Counter'). Required for create, update, remove, and approve. Optional for query."
                },
                "contact_name": {
                    "type": "string",
                    "description": "The full name of the contact. Required for create, update, and remove."
                },
                "pathway_name": {
                    "type": "string",
                    "description": "Optional pathway name (e.g. 'Dynamic Leadership') to update or set speech details."
                },
                "project_name": {
                    "type": "string",
                    "description": "Optional project name (e.g. 'Ice Breaker') to update or set speech details."
                },
                "speech_title": {
                    "type": "string",
                    "description": "Optional speech title to update or set."
                },
                "speaker_name": {
                    "type": "string",
                    "description": "Optional target name. For roles tied to a specific speaker or session (e.g. 'Individual Evaluator' evaluating a specific Prepared Speaker), specify the name of that speaker."
                }
            },
            "required": ["action", "meeting_identifier"]
        }
    },
    {
        "name": "manage_meeting_sessions",
        "description": "Add, update, move, delete, or query agenda sessions (rows) in a meeting. Use this to add a new session like a 3rd Prepared Speech to an existing meeting's agenda. Read-only 'query' returns sessions with companion evaluation links. For 'add' with session_type='Prepared Speech', you MUST also call this tool again with action='add' for the companion 'Evaluation' (and ideally an 'Individual Evaluator') in the same response — chain them, do not prompt the user. See tools.md section 9 for the full companion-chain rule. Refuses on running/finished meetings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "The action to perform: 'add' (insert a new session row), 'update' (modify an existing session), 'move' (reorder a session), 'delete' (remove a session), 'query' (list or deep-dive sessions)."
                },
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number (e.g. '350') or meeting date (YYYY-MM-DD). Required for all actions."
                },
                "session_log_id": {
                    "type": "integer",
                    "description": "Used by update/move/delete/query. The numeric ID of the target SessionLog row. Preferred over fuzzy lookup."
                },
                "session_type": {
                    "type": "string",
                    "description": "Used by add (required) and by update/move/delete/query (optional fuzzy lookup). The SessionType.Title, e.g. 'Prepared Speech', 'Evaluation', 'Individual Evaluator', 'Table Topics Speaker'."
                },
                "slot_index": {
                    "type": "integer",
                    "description": "Used by update/move/delete/query when session_log_id is not known. 1-based position among rows of the matching session_type in the meeting."
                },
                "owner_name": {
                    "type": "string",
                    "description": "Used by add (optional pre-assign) and by update (owner reassignment) / query (filter). Full name of the contact."
                },
                "session_title": {
                    "type": "string",
                    "description": "Used by add/update. Custom label for the session row. Format depends on session_type (the agenda UI has hard-coded rendering rules): (a) 'Evaluation' rows: pass only the speaker's name or speech title (e.g. 'Shark Liu' or 'Ice Breaker'). The UI auto-prepends 'Evaluator for ', so passing 'Evaluation for Shark Liu' or 'Evaluator for Shark Liu' would render as 'Evaluator for Evaluation for Shark Liu' / 'Evaluator for Evaluator for Shark Liu'. (b) 'Individual Evaluator' rows: pass the full 'Evaluator for <Speaker Name>' phrase (the UI does not auto-prepend). (c) 'Prepared Speech' / 'Pathway Speech' / 'Presentation': pass the speech title — the UI wraps it in quotes. (d) Anything else: pass a human-readable label."
                },
                "pathway": {
                    "type": "string",
                    "description": "Used by add/update. Pathway name (e.g. 'Dynamic Leadership'). Defaults to owner's current path or 'Non Pathway'."
                },
                "project_id": {
                    "type": "integer",
                    "description": "Used by add/update. Numeric Project ID (e.g. 60 for Generic, or a specific project). Omit to let it default."
                },
                "duration_min": {
                    "type": "integer",
                    "description": "Used by add/update. Minimum duration in minutes. Defaults to the SessionType's default."
                },
                "duration_max": {
                    "type": "integer",
                    "description": "Used by add/update. Maximum duration in minutes. Defaults to the SessionType's default."
                },
                "is_hidden": {
                    "type": "boolean",
                    "description": "Used by add/update. Whether the row is a hidden/section row (no start-time accumulation)."
                },
                "insert_position": {
                    "type": "integer",
                    "description": "Used by add/move. 1-based seq. If omitted on add, defaults to the end of the matching session_type's block, or end of meeting. If omitted on move, supply after_session_log_id or before_session_log_id."
                },
                "after_session_log_id": {
                    "type": "integer",
                    "description": "Used by move. Insert after this session log (e.g. 'end' to move to the end)."
                },
                "before_session_log_id": {
                    "type": "integer",
                    "description": "Used by move. Insert before this session log (e.g. 'start' to move to the beginning)."
                },
                "include_companions": {
                    "type": "boolean",
                    "description": "Used by query. Default true. When true, Prepared Speech rows include companion evaluation/evaluator log IDs."
                }
            },
            "required": ["action", "meeting_identifier"]
        }
    },
    {
        "name": "update_project_details",
        "description": "Update the project, pathway, and speech title details of a booked speaker or waitlisted speaker for a meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number (e.g. '350') or meeting date (YYYY-MM-DD). Required."
                },
                "contact_name": {
                    "type": "string",
                    "description": "The full name of the member/speaker. Required."
                },
                "project_code": {
                    "type": "string",
                    "description": "Optional project code (e.g. 'EH4.1', 'PM1.1', 'TM1.0'). Maps automatically to the correct project and pathway. If multiple projects share this code (like Electives), the tool fails and returns all matching projects so the user can choose or provide a project_name."
                },
                "project_name": {
                    "type": "string",
                    "description": "Optional project name (e.g. 'Ice Breaker')."
                },
                "speech_title": {
                    "type": "string",
                    "description": "Optional speech title to set."
                },
                "pathway_name": {
                    "type": "string",
                    "description": "Optional pathway name (e.g. 'Engaging Humor')."
                }
            },
            "required": ["meeting_identifier", "contact_name"]
        }
    }
]

class ChatService:
    """
    Service that interacts with MiniMax Anthropic-compatible API endpoint.
    """
    _tools_guidelines = None

    @classmethod
    def get_tools_guidelines(cls):
        if cls._tools_guidelines is None:
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tools_md_path = os.path.join(current_dir, 'tools.md')
            try:
                if os.path.exists(tools_md_path):
                    with open(tools_md_path, 'r', encoding='utf-8') as f:
                        cls._tools_guidelines = f.read()
                else:
                    cls._tools_guidelines = ""
            except Exception as e:
                current_app.logger.error(f"Error loading tools.md guidelines: {str(e)}")
                cls._tools_guidelines = ""
        return cls._tools_guidelines


    @staticmethod
    def get_client():
        api_key = current_app.config.get('ANTHROPIC_API_KEY')
        base_url = current_app.config.get('ANTHROPIC_BASE_URL')
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not configured.")
            
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)

    @classmethod
    def _messages_create_with_retry(cls, client, **kwargs):
        import time
        import anthropic
        
        api_retries = 0
        max_api_retries = 5
        backoff = 1.0
        
        while True:
            try:
                return client.messages.create(**kwargs)
            except anthropic.RateLimitError as e:
                api_retries += 1
                if api_retries > max_api_retries:
                    current_app.logger.error(f"RateLimitError: Max retries exceeded. Request parameters: {kwargs}")
                    raise e
                current_app.logger.warning(f"RateLimitError encountered. Retrying in {backoff} seconds... (Attempt {api_retries}/{max_api_retries})")
                time.sleep(backoff)
                backoff *= 2.0
            except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
                api_retries += 1
                if api_retries > max_api_retries:
                    current_app.logger.error(f"Connection/Timeout Error: Max retries exceeded. Request parameters: {kwargs}")
                    raise e
                current_app.logger.warning(f"Transient API error: {str(e)}. Retrying in {backoff} seconds... (Attempt {api_retries}/{max_api_retries})")
                time.sleep(backoff)
                backoff *= 1.5

    @classmethod
    def generate_summary(cls, previous_summary, new_messages_text):
        """
        Uses the LLM to update or create a running summary of the chat history.
        """
        client = cls.get_client()
        model_name = current_app.config.get('ANTHROPIC_MODEL', 'MiniMax-M3')
        
        system_prompt = (
            "You are an assistant tasked to maintain a running summary of a chat conversation.\n"
            "Keep the summary concise (under 300 words), focusing on actions taken, "
            "confirmed meeting roles, or user preferences.\n"
            "Integrate the new messages into the previous summary dynamically."
        )
        
        user_prompt = f"Previous summary:\n{previous_summary or 'No previous summary.'}\n\nNew messages:\n{new_messages_text}\n\nProvide the updated summary:"
        
        try:
            response = cls._messages_create_with_retry(
                client,
                model=model_name,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1000,
                temperature=0.0
            )
            # Retrieve text response
            text_block = next((block.text for block in response.content if block.type == "text"), "")
            return text_block.strip()
        except Exception as e:
            current_app.logger.error(f"Error generating chat summary: {str(e)}")
            if previous_summary:
                return previous_summary + "\n[Error updating summary context]"
            return "[Error generating summary context]"

    @staticmethod
    def get_system_prompt(user, club_id, locale):
        club = db.session.get(Club, club_id)
        club_name = club.club_name if club else "Unknown Club"
        
        contact = user.get_contact(club_id)
        user_name = contact.Name if contact else user.username
        role_name = user.primary_role_name
        
        today = datetime.now().strftime('%Y-%m-%d %A')

        prompt = (
            f"You are the Memory Maker AI Assistant for '{club_name}' Toastmasters Club.\n"
            f"You assist club officers and members in managing meetings, role bookings, rosters, and educational achievements.\n\n"
            f"Context Info:\n"
            f"- Today is: {today}\n"
            f"- Current User: {user_name} (Role level: {role_name})\n"
            f"- User Locale: {locale}\n\n"
            f"Rules:\n"
            f"1. You must respond in the language set by the language switch toggler, which is specified by User Locale: if 'zh_CN', you must always respond in Chinese; if 'en', you must always respond in English. Do not follow the language of the user's message if it differs from the language switch toggler. Translate any retrieved database information, tool outputs, meeting details, and agenda tables to the target language (Chinese for 'zh_CN', English for 'en') when replying to the user.\n"
            f"2. You do not have direct database access; any past actions or info retrieval shown in the chat history was performed by executing tools. You MUST always execute the appropriate function/tool to retrieve database details, roles, roster checks, or voting results, or to make operational/status modifications (e.g. starting or finishing a meeting, assigning or cancelling roles, checking in contacts, creating meetings, or recording achievements) for the current request. Never guess, assume, or hallucinate database records, contacts, roles, or voting results under any circumstances.\n"
            f"3. When a tool returns success=False with helpful guidance about missing parameters or available options, extract and clearly present that guidance to the user. Do NOT say you were unable to execute. Instead, explain specifically what additional information is needed and list the available options. For example: 'To create a meeting, I need to know which template you prefer. Available options are: Keynote Speech, Speech Marathon, etc.'\n"
            f"4. When creating a meeting, if the user doesn't specify a template, you MUST ask the user to choose from available templates returned by the tool.\n"
            f"5. If a contact name is ambiguous, call the search contact tool first or ask the user for clarification.\n"
            f"6. Always confirm the execution of operational changes (creating, assigning, checking in, completions, status updates) in a polite, concise manner, but only after executing the appropriate tool and verifying its success.\n"
            f"7. Never claim, assume, or confirm that an action succeeded or was completed unless the tool execution returned `success=True`. If the tool failed, report the failure reason faithfully to the user. Specifically, starting a meeting requires calling `update_meeting_status` with `status='running'`, and finishing/ending/completing a meeting requires calling `update_meeting_status` with `status='finished'`.\n"
            f"8. The scope of this chat window is strictly limited to the current club '{club_name}' (ID: {club_id}). You must only query, create, or modify meetings, contacts, roles, achievements, or officers that belong to this club.\n"
            f"9. Never disclose any internal database IDs (such as database meeting ID, contact ID, session log ID, etc.) in your messages to the user. These are internal database primary keys and should not be shown. Only refer to meetings by their Meeting Number (e.g. Meeting #983)."
        )
        return prompt

    @staticmethod
    def get_query_context(message_text, club_id):
        """
        Queries the database for relevant meetings or contacts matching keywords 
        in the user's query and returns a structured context string to guide the LLM.
        """
        if not message_text:
            return ""
            
        context_parts = []
        message_lower = message_text.lower()
        import re
        
        # 1. Look for meeting numbers (e.g. #973, 973)
        meeting_nums = re.findall(r'#?(\d+)', message_text)
        if meeting_nums:
            from app.models import Meeting
            for num_str in meeting_nums:
                try:
                    num = int(num_str)
                    meeting = Meeting.query.filter_by(club_id=club_id, Meeting_Number=num).first()
                    if meeting:
                        context_parts.append(
                            f"- Meeting #{meeting.Meeting_Number} exists (Date: {meeting.Meeting_Date}, Status: {meeting.status}, Title: '{meeting.Meeting_Title or 'N/A'}')"
                        )
                except ValueError:
                    continue
                    
        # 2. Look for "upcoming" or "next" meeting query
        if any(w in message_lower for w in {'upcoming', 'next', '下一次', '下次', '后面', '新', '创建'}):
            from app.models import Meeting
            upcoming = Meeting.query.filter(
                Meeting.club_id == club_id,
                Meeting.status != 'finished',
                Meeting.status != 'cancelled'
            ).order_by(Meeting.Meeting_Date.asc()).limit(3).all()
            for m in upcoming:
                context_parts.append(
                    f"- Upcoming/Active Meeting #{m.Meeting_Number}: Date={m.Meeting_Date}, Status='{m.status}', Title='{m.Meeting_Title or 'N/A'}'"
                )

        # 3. Look for potential contact names (capitalized words or specific name substrings)
        # Match alphabetical words >= 2 chars, or Chinese characters
        words = re.findall(r'[A-Za-z\u4e00-\u9fa5]+', message_text)
        potential_names = []
        skip_words = {
            'meeting', 'agenda', 'role', 'assign', 'cancel', 'check', 'show', 'tally', 'results', 
            'voting', 'vote', 'hello', 'who', 'what', 'when', 'where', 'list', 'details', 'info', 
            'the', 'votign', 'results', 'of', 'for', 'to', 'in', 'tme', 'speaker', 'evaluator',
            '会议', '分配', '结果', '查询', '角色', '签到'
        }
        for w in words:
            if w.lower() in skip_words:
                continue
            if len(w) >= 2 or re.match(r'[\u4e00-\u9fa5]', w):
                potential_names.append(w)
                
        if potential_names:
            from app.models import Contact
            from app.models.contact_club import ContactClub
            for name in potential_names:
                contacts = Contact.query.join(ContactClub).filter(
                    ContactClub.club_id == club_id,
                    Contact.Name.like(f"%{name}%")
                ).limit(5).all()
                for c in contacts:
                    context_parts.append(
                        f"- Contact in directory: Name='{c.Name}' (ID: {c.id}, Type: '{c.Type}', Email: '{c.Email or 'N/A'}')"
                    )
                    
        if context_parts:
            # Sort to keep prompt output deterministic for identical inputs
            sorted_context = sorted(list(set(context_parts)))
            return "\n[Database Context for Current Query]:\n" + "\n".join(sorted_context) + "\n"
            
        return ""

    @staticmethod
    def should_enforce_tools(message_text):
        """
        Determines whether the user's message requests factual data, actions, 
        or lookups that MUST use database tools rather than allowing LLM hallucination.
        Supports both English and Chinese triggers.
        """
        if not message_text:
            return False
            
        message_lower = message_text.lower()
        
        # Generic greetings and meta-conversation that don't need tools
        greetings = {'hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening', 'thanks', 'thank you', 'ok', 'okay', 'yes', 'no'}
        if message_lower.strip() in greetings:
            return False
            
        # Self-identification or help queries
        meta_words = {'who are you', 'what is your name', 'what can you do', 'how can you help', 'help me', 'show help', 'chat help'}
        if any(w in message_lower for w in meta_words):
            return False
            
        # Standard English indicators for database queries, lookups, or actions
        english_triggers = [
            'meeting', 'agenda', 'schedule', 'template',
            'role', 'book', 'assign', 'unassign', 'cancel',
            'contact', 'member', 'guest', 'officer', 'search', 'find', 'lookup',
            'check in', 'check-in', 'checkin', 'roster', 'ticket',
            'complete', 'completion', 'level', 'pathway', 'achievement',
            'vote', 'voting', 'votign', 'tally', 'tallies', 'result', 'winner', 'award',
            'status', 'publish', 'start', 'finish',
            'tme', 'speaker', 'evaluator', 'topicsmaster',
            'timer', 'counter', 'grammarian', 'general evaluator',
            'toastmaster', 'toastmasters', 'prepared speaker', 'topics speaker',
            'individual evaluator', 'photographer', 'welcome officer',
            'who', 'what', 'where', 'when', 'show', 'list', 'details', 'info',
            'excomm', 'waitlist', 'update', 'set', 'president', 'vpe', 'vpm', 'vppr',
            'secretary', 'treasurer', 'saa', 'ipp'
        ]
        
        # Standard Chinese indicators for database queries, lookups, or actions
        chinese_triggers = [
            '会议', '日程', '模板',
            '角色', '预订', '分配', '指派', '取消',
            '联系人', '会员', '嘉宾', '官员', '搜索', '查找', '查询',
            '签到',
            '完成', '级别', '路径', '成就',
            '投票', '计票', '结果', '赢家', '获奖', '得票',
            '状态', '发布', '开始', '结束',
            '谁', '什么', '哪里', '什么时候', '显示', '列表',
            '主持', '点评', '演讲', '即兴',
            '执委', '候补', '等候', '排队',
            '主持人', '时间官', '语法官', '阿哈计数器', '阿计数器', '摄影官', '接待官',
            '更新', '修改', '设置', '会长', '教育', '公关', '秘书', '财务', '接待', '安全'
        ]
        
        # Check if any English database trigger word is in the message
        if any(trigger in message_lower for trigger in english_triggers):
            return True
            
        # Check if any Chinese database trigger word is in the message
        if any(trigger in message_lower for trigger in chinese_triggers):
            return True
            
        # Check for numbers (like meeting numbers #973) or date-like patterns
        import re
        if re.search(r'\d+', message_text):
            return True
            
        return False

    @classmethod
    def process_chat_completion(cls, chat_history_list, user, club_id, locale):
        """
        Processes a full conversation cycle using Anthropic protocol.
        """
        client = cls.get_client()
        model_name = current_app.config.get('ANTHROPIC_MODEL', 'MiniMax-M3')

        # Get the latest user message text for tool choice enforcement detection
        user_message = ""
        for msg in reversed(chat_history_list):
            if msg.role == 'user':
                user_message = msg.content
                break

        # Stop and warn the user for unrecognized queries to reduce database hallucination
        if user_message:
            is_enforced = cls.should_enforce_tools(user_message)
            message_lower = user_message.lower().strip()
            greetings = {'hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening', 'thanks', 'thank you', 'ok', 'okay', 'yes', 'no'}
            meta_words = {'who are you', 'what is your name', 'what can you do', 'how can you help', 'help me', 'show help', 'chat help'}
            
            is_greeting = message_lower in greetings
            is_meta = any(w in message_lower for w in meta_words)
            
            # Check if the user is replying to a clarification question from the assistant
            is_clarification_reply = False
            found_user = False
            for msg in reversed(chat_history_list):
                if not found_user:
                    if msg.role == 'user' and msg.content == user_message:
                        found_user = True
                    continue
                if msg.role == 'assistant':
                    content = msg.content or ""
                    content_lower = content.lower()
                    if (any(q in content for q in ["哪位", "确认", "哪个", "谁", "请问", "请选择", "输入"]) or
                        any(q in content_lower for q in ["which", "whom", "who", "confirm", "select", "please specify", "please choose"]) or
                        content.strip().endswith("?") or content.strip().endswith("？")):
                        is_clarification_reply = True
                    break
            
            if not is_enforced and not is_greeting and not is_meta and not is_clarification_reply:
                if locale == 'zh_CN':
                    warning_message = "抱歉，我无法识别您请求中的具体数据库操作或查询。请使用明确的关键词（例如'分配'、'取消'、'日程'、'结果'等），或输入 `/help` 查看可用命令。"
                else:
                    warning_message = "I'm sorry, I couldn't identify the specific database action or query in your request. Please use clear keywords (such as 'assign', 'cancel', 'schedule', 'results'), or type `/help` to see available commands."
                return warning_message, []

        from app.services.chat_history_context import ChatHistoryContext

        # Run within the ChatHistoryContext manager to load messages, database context, and running summary dynamically
        with ChatHistoryContext(user, club_id, chat_history_list=chat_history_list, user_message=user_message, locale=locale) as chat_ctx:
            system_prompt = chat_ctx.system_prompt
            messages = chat_ctx.messages

        # Ensure history is not empty and starts with user role if present
        if not messages:
            messages.append({"role": "user", "content": "Hello"})

        # Append tool and language reminder to the last user message to enforce rules
        if messages and messages[-1]["role"] == "user":
            lang_reminder = (
                f"\n(System: Remember, you must respond in Chinese because the User Locale is '{locale}'.)"
                if locale == 'zh_CN' else
                f"\n(System: Remember, you must respond in English because the User Locale is '{locale}'.)"
            )
            messages[-1]["content"] += (
                f"\n(System: You do not have direct database access. You MUST execute the appropriate function/tool to retrieve or modify any database details, status, dates, or results. Never guess or hallucinate records. If you perform an action, you must call its tool first and verify it succeeded.)"
                f"{lang_reminder}"
            )

        executed_tools = []
        max_turns = 5

        # Determine if we should enforce tool usage at the API level (any vs auto)
        is_enforced = cls.should_enforce_tools(user_message)
        tool_choice = {"type": "any"} if is_enforced else {"type": "auto"}

        retry_count = 0
        max_retries = 2
        
        while retry_count < max_retries:
            import copy
            messages_run = copy.deepcopy(messages)
            executed_tools = []
            turn = 0
            text_response = ""
            
            while turn < max_turns:
                turn += 1
                
                response = cls._messages_create_with_retry(
                    client,
                    model=model_name,
                    system=system_prompt,
                    messages=messages_run,
                    tools=CHAT_TOOLS,
                    tool_choice=tool_choice,
                    max_tokens=2000,
                    temperature=0.0
                )
                # Downgrade tool_choice to auto for subsequent turns
                tool_choice = {"type": "auto"}

                # Check if model wants to call tools
                if response.stop_reason == "tool_use":
                    # Find all tool uses in response blocks
                    tool_uses = [block for block in response.content if block.type == "tool_use"]
                    
                    # Append assistant's response (which contains the tool requests) to the history
                    messages_run.append({
                        "role": "assistant",
                        "content": response.content
                    })

                    # Process tool calls
                    tool_results_content = []
                    for tu in tool_uses:
                        tool_name = tu.name
                        params = tu.input # Anthropic parses arguments into dict automatically

                        # Execute tool locally
                        tool_result = ChatToolExecutor.execute(tool_name, params, user, club_id)

                        # Audit tool execution (including result)
                        executed_tools.append({
                            'id': tu.id,
                            'name': tool_name,
                            'arguments': params,
                            'result': tool_result
                        })
                        
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": json.dumps(tool_result)
                        })

                    # Append tool results as a single user message containing tool results
                    messages_run.append({
                        "role": "user",
                        "content": tool_results_content
                    })

                else:
                    # Text response (no tool uses)
                    # Find the text content block
                    text_block = next((block.text for block in response.content if block.type == "text"), "")
                    text_response = text_block
                    break
                    
            if is_enforced and not executed_tools:
                retry_count += 1
                current_app.logger.warning(f"Enforced database query but model returned text directly without calling tools. Retrying... (Attempt {retry_count}/{max_retries})")
                
                # Insert warning to enforce tool usage
                if messages and messages[-1]["role"] == "user":
                    messages[-1]["content"] += "\n(System Warning: You did not call any database tools. You MUST invoke a database tool to query or perform this action. Do not reply with text success or failure directly.)"
                
                # Reset tool_choice for retry
                tool_choice = {"type": "any"}
                continue
            else:
                if turn >= max_turns and not text_response:
                    return "The request was too complex and reached the maximum execution limit.", executed_tools
                # Allow LLM to process tool results before returning
                if executed_tools and not text_response:
                    continue
                # If a tool returned a failure with a guidance message and the
                # LLM did not produce a text response, fall back to surfacing
                # the tool's guidance. Otherwise trust the LLM's reply.
                if not text_response:
                    for tool in executed_tools:
                        tool_result = tool.get('result', {})
                        if tool_result.get('success') is False and tool_result.get('message'):
                            text_response = tool_result['message']
                            break
                return text_response, executed_tools

        # Retries exhausted - let LLM generate constructive feedback from tool guidance
        for tool in executed_tools:
            tool_result = tool.get('result', {})
            if not tool_result.get('success') and tool_result.get('message'):
                # Inject tool's guidance as a user message for LLM to formulate a helpful response
                guidance_msg = tool_result['message']
                lang_suffix = " 请您根据情况给用户提供帮助。" if locale == 'zh_CN' else " Please provide helpful guidance to the user based on this information."
                messages_run.append({
                    "role": "user",
                    "content": f"System Note: {guidance_msg}{lang_suffix}"
                })
                # Give LLM one more turn to respond constructively
                response = client.messages.create(
                    model=model_name,
                    system=system_prompt,
                    messages=messages_run,
                    tools=CHAT_TOOLS,
                    tool_choice={"type": "auto"},
                    max_tokens=2000,
                    temperature=0.0
                )
                text_block = next((block.text for block in response.content if block.type == "text"), "")
                if text_block:
                    return text_block, executed_tools
                # Fallback to guidance message if LLM still didn't respond helpfully
                return guidance_msg, executed_tools

        # No guidance found, return generic error
        if locale == 'zh_CN':
            return "抱歉，系统未能成功执行数据库操作工具。请尝试输入更具体的信息，或刷新页面后重试。", []
        else:
            return "I'm sorry, I was unable to execute the database tool for your request. Please try with more specific details, or refresh and try again.", []
