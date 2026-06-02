import json
from flask import current_app
from app import db, cache
from app.models import ChatMessage

class ChatHistoryContext:
    """
    Context manager that manages chat history dynamically.
    Partitions the chat history into active messages and older messages,
    generates/maintains a running summary for older messages,
    and dynamically injects database context and summary into the system prompt.
    """
    def __init__(self, user, club_id, chat_history_list=None, user_message=None, locale='en'):
        self.user = user
        self.club_id = club_id
        self.chat_history_list = chat_history_list
        self.user_message = user_message
        self.locale = locale
        
        self.summary = ""
        self.messages = []
        self.system_prompt = ""
        self.executed_tools = []
        self.active_limit = 20

    def __enter__(self):
        from app.services.chat_service import ChatService
        
        # 1. Determine active messages limit from config
        self.active_limit = current_app.config.get('CHAT_HISTORY_ACTIVE_LIMIT', 20)
        
        # 2. Fetch all user/assistant chat messages in chronological order
        if self.chat_history_list is not None:
            all_messages = [
                msg for msg in self.chat_history_list
                if msg.role in ['user', 'assistant']
            ]
        else:
            all_messages = ChatMessage.query.filter_by(
                user_id=self.user.id,
                club_id=self.club_id
            ).filter(
                ChatMessage.role.in_(['user', 'assistant'])
            ).order_by(ChatMessage.timestamp.asc()).all()

        # Filter out failed/hallucinated database turns to avoid biasing the model
        filtered_messages = []
        i = 0
        n = len(all_messages)
        while i < n:
            msg = all_messages[i]
            
            # Check if this is a user message followed by an assistant message
            if msg.role == 'user' and i + 1 < n and all_messages[i + 1].role == 'assistant':
                user_msg = msg
                assistant_msg = all_messages[i + 1]
                
                # Check if this was a database query/action request
                was_db_req = ChatService.should_enforce_tools(user_msg.content)
                # Check if it executed any database tools
                executed_any = bool(assistant_msg.tool_calls)
                
                if was_db_req and not executed_any:
                    # This was a database request that failed to execute tools (e.g. hallucinated text/error).
                    # We exclude this untrustworthy turn from the active history.
                    i += 2
                    continue
            
            filtered_messages.append(msg)
            i += 1
            
        all_messages = filtered_messages

        # 3. Partition into active messages and older messages
        older_messages = []
        active_messages_objs = []
        
        active_limit = self.active_limit
        if ChatService.should_enforce_tools(self.user_message):
            # For database actions/queries, restrict active history to prevent the model
            # from being biased by historical plain-text assistant responses.
            active_limit = min(5, active_limit)
            
        if len(all_messages) > active_limit:
            older_messages = all_messages[:-active_limit]
            active_messages_objs = all_messages[-active_limit:]
        else:
            active_messages_objs = all_messages

        # Convert active message objects to Anthropic messages payload
        self.messages = []
        for msg in active_messages_objs:
            if msg.role == 'user':
                self.messages.append({
                    "role": "user",
                    "content": msg.content
                })
            elif msg.role == 'assistant':
                has_results = False
                if msg.tool_calls:
                    try:
                        tool_runs = json.loads(msg.tool_calls)
                        has_results = any('result' in run for run in tool_runs)
                    except Exception:
                        tool_runs = []
                else:
                    tool_runs = []
                    
                if tool_runs and has_results:
                    # 1. Tool Use Message (assistant role)
                    assistant_content = []
                    for run in tool_runs:
                        assistant_content.append({
                            "type": "tool_use",
                            "id": run['id'],
                            "name": run['name'],
                            "input": run['arguments']
                        })
                    self.messages.append({
                        "role": "assistant",
                        "content": assistant_content
                    })
                    
                    # 2. Tool Result Message (user role)
                    tool_results_content = []
                    for run in tool_runs:
                        if 'result' in run:
                            tool_results_content.append({
                                "type": "tool_result",
                                "tool_use_id": run['id'],
                                "content": json.dumps(run['result'])
                            })
                    if tool_results_content:
                        self.messages.append({
                            "role": "user",
                            "content": tool_results_content
                        })
                        
                    # 3. Final Text Response (assistant role)
                    self.messages.append({
                        "role": "assistant",
                        "content": msg.content
                    })
                else:
                    self.messages.append({
                        "role": "assistant",
                        "content": msg.content
                    })

        # 4. Handle summary of older messages
        if older_messages:
            cache_key = f"chat_summary_{self.user.id}_{self.club_id}"
            cached_data = cache.get(cache_key)
            
            # Determine which older messages need summarizing (ignore messages without IDs in test/edge cases)
            last_msg_id = cached_data.get('last_msg_id', 0) if cached_data else 0
            messages_to_add = [
                msg for msg in older_messages
                if msg.id is not None and msg.id > last_msg_id
            ]
            
            if messages_to_add:
                # Need to update/generate the summary
                previous_summary = cached_data.get('summary', '') if cached_data else ''
                
                # Convert new messages to simple text format for summarizer
                new_msgs_text = ""
                for msg in messages_to_add:
                    new_msgs_text += f"{msg.role}: {msg.content}\n"
                
                # Generate updated summary via LLM
                updated_summary = ChatService.generate_summary(previous_summary, new_msgs_text)
                
                # Cache the updated summary
                cache_data = {
                    'summary': updated_summary,
                    'last_msg_id': messages_to_add[-1].id
                }
                cache.set(cache_key, cache_data, timeout=86400) # cache for 1 day
                self.summary = updated_summary
            else:
                self.summary = cached_data.get('summary', '') if cached_data else ''

        # 5. Get dynamic database context and apply ceiling limits
        db_context = ChatService.get_query_context(self.user_message, self.club_id)
        # Apply character ceiling to database context to avoid prompt bloat (max 3000 chars)
        if db_context and len(db_context) > 3000:
            db_context = db_context[:3000] + "\n[Context truncated due to size limit...]"

        # 6. Build the dynamic system prompt
        base_prompt = ChatService.get_system_prompt(self.user, self.club_id, self.locale)
        
        system_prompt_parts = [base_prompt]
        if self.summary:
            # Apply safety ceiling to summary size (max 4000 chars)
            summary_clean = self.summary if len(self.summary) <= 4000 else self.summary[:4000] + "..."
            summary_section = (
                f"\n\n[Summary of older conversation in this session]:\n"
                f"{summary_clean}"
            )
            system_prompt_parts.append(summary_section)
            
        if db_context:
            system_prompt_parts.append(db_context)
            
        # Dynamically inject tool guidelines if we might use tools
        if ChatService.should_enforce_tools(self.user_message):
            tools_guidelines = ChatService.get_tools_guidelines()
            if tools_guidelines:
                system_prompt_parts.append(tools_guidelines)
                
        self.system_prompt = "\n\n".join(system_prompt_parts)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean resources or log errors if needed
        pass
