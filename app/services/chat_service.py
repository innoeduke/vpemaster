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
        "name": "assign_role",
        "description": "Assign a contact to a role for a specific meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number (e.g. '350') or meeting date (YYYY-MM-DD)."
                },
                "role_name": {
                    "type": "string",
                    "description": "Name of the role (e.g. 'Ah Counter', 'Prepared Speaker')."
                },
                "contact_name": {
                    "type": "string",
                    "description": "The full name of the contact being assigned."
                }
            },
            "required": ["meeting_identifier", "role_name", "contact_name"]
        }
    },
    {
        "name": "cancel_role",
        "description": "Cancel a contact's role assignment for a meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_identifier": {
                    "type": "string",
                    "description": "Meeting number or date."
                },
                "role_name": {
                    "type": "string",
                    "description": "The role to cancel."
                },
                "contact_name": {
                    "type": "string",
                    "description": "The contact's name."
                }
            },
            "required": ["meeting_identifier", "role_name", "contact_name"]
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
                "issue_date": {
                    "type": "string",
                    "description": "Optional date in YYYY-MM-DD format."
                }
            },
            "required": ["contact_name", "pathway_name", "level"]
        }
    },
    {
        "name": "get_pathway_status",
        "description": "Get a contact's current registered pathways and completed levels.",
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
        "description": "Get detailed metadata for a specific meeting.",
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
        "name": "get_role_assignments",
        "description": "Get the current role bookings/assignments list for a meeting.",
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
        "name": "get_available_roles",
        "description": "Get all unbooked role slots for a specific meeting.",
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
        "description": "Get voting tallies and winners for a meeting.",
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
    }
]

class ChatService:
    """
    Service that interacts with MiniMax Anthropic-compatible API endpoint.
    """

    @staticmethod
    def get_client():
        api_key = current_app.config.get('ANTHROPIC_API_KEY')
        base_url = current_app.config.get('ANTHROPIC_BASE_URL')
        
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not configured.")
            
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)

    @staticmethod
    def get_system_prompt(user, club_id, locale):
        club = db.session.get(Club, club_id)
        club_name = club.club_name if club else "Unknown Club"
        
        contact = user.get_contact(club_id)
        user_name = contact.Name if contact else user.username
        role_name = user.primary_role_name
        
        today = datetime.now().strftime('%Y-%m-%d %A')

        prompt = (
            f"You are the VPE Master AI Assistant for '{club_name}' Toastmasters Club.\n"
            f"You assist club officers and members in managing meetings, role bookings, rosters, and educational achievements.\n\n"
            f"Context Info:\n"
            f"- Today is: {today}\n"
            f"- Current User: {user_name} (Role level: {role_name})\n"
            f"- User Locale: {locale}\n\n"
            f"Rules:\n"
            f"1. You must respond in the same language the user is speaking (e.g. English or Chinese).\n"
            f"2. Use the available functions to retrieve info or make updates. Do not assume or hallucinate info you do not have.\n"
            f"3. When creating a meeting, if the user doesn't specify a template, you MUST ask the user to choose from available templates returned by the tool.\n"
            f"4. If a contact name is ambiguous, call the search contact tool first or ask the user for clarification.\n"
            f"5. Always confirm the execution of operational changes (creating, assigning, checking in, completions) in a polite, concise manner."
        )
        return prompt

    @classmethod
    def process_chat_completion(cls, chat_history_list, user, club_id, locale):
        """
        Processes a full conversation cycle using Anthropic protocol.
        """
        client = cls.get_client()
        model_name = current_app.config.get('ANTHROPIC_MODEL', 'MiniMax-M3')

        # system prompt passed separately in Anthropic
        system_prompt = cls.get_system_prompt(user, club_id, locale)
        
        # Build messages history (filter out any system messages from DB, only user/assistant)
        messages = []
        for msg in chat_history_list[-15:]:
            if msg.role in ['user', 'assistant']:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Ensure history is not empty and starts with user role if present
        # If there's no preceding messages, Claude expects user role first
        if not messages:
            # Fallback welcome is triggered client side, but just in case:
            messages.append({"role": "user", "content": "Hello"})

        executed_tools = []
        max_turns = 5
        turn = 0

        while turn < max_turns:
            turn += 1
            
            response = client.messages.create(
                model=model_name,
                system=system_prompt,
                messages=messages,
                tools=CHAT_TOOLS,
                max_tokens=2000,
                temperature=0.0
            )

            # Check if model wants to call tools
            if response.stop_reason == "tool_use":
                # Find all tool uses in response blocks
                tool_uses = [block for block in response.content if block.type == "tool_use"]
                
                # Append assistant's response (which contains the tool requests) to the history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Process tool calls
                tool_results_content = []
                for tu in tool_uses:
                    tool_name = tu.name
                    params = tu.input # Anthropic parses arguments into dict automatically

                    # Audit tool execution
                    executed_tools.append({
                        'id': tu.id,
                        'name': tool_name,
                        'arguments': params
                    })

                    # Execute tool locally
                    tool_result = ChatToolExecutor.execute(tool_name, params, user, club_id)
                    
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(tool_result)
                    })

                # Append tool results as a single user message containing tool results
                messages.append({
                    "role": "user",
                    "content": tool_results_content
                })

            else:
                # Text response (no tool uses)
                # Find the text content block
                text_block = next((block.text for block in response.content if block.type == "text"), "")
                return text_block, executed_tools

        return "The request was too complex and reached the maximum execution limit.", executed_tools
