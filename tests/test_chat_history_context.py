import pytest
from unittest.mock import MagicMock, patch
from flask import current_app
from app import db, cache
from app.models import ChatMessage, User, Club
from app.services.chat_history_context import ChatHistoryContext
from app.services.chat_service import ChatService

def test_chat_history_partitioning(app, staff_user, default_club):
    """Test that ChatHistoryContext correctly partitions messages based on CHAT_HISTORY_ACTIVE_LIMIT."""
    with app.app_context():
        # Setup mock active limit config to 3
        app.config['CHAT_HISTORY_ACTIVE_LIMIT'] = 3

        # Create 5 chat messages
        messages = [
            ChatMessage(id=1, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg A'),
            ChatMessage(id=2, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg B'),
            ChatMessage(id=3, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg C'),
            ChatMessage(id=4, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg D'),
            ChatMessage(id=5, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg E'),
        ]

        # We mock ChatService.generate_summary to avoid real LLM call
        with patch.object(ChatService, 'generate_summary', return_value="Mock summary of Msg A, B") as mock_summarize:
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages, locale='en') as ctx:
                # Active limit is 3, so last 3 messages are active
                assert len(ctx.messages) == 3
                assert ctx.messages[0]['content'] == 'Msg C'
                assert ctx.messages[1]['content'] == 'Msg D'
                assert ctx.messages[2]['content'] == 'Msg E'

                # Older limit messages are first 2
                # ChatHistoryContext should call generate_summary
                mock_summarize.assert_called_once()
                assert ctx.summary == "Mock summary of Msg A, B"

def test_chat_summary_caching_and_incremental_update(app, staff_user, default_club):
    """Test that summary is cached and incrementally updated with new older messages."""
    cache_key = f"chat_summary_{staff_user.id}_{default_club.id}"
    
    with app.app_context():
        cache.clear()
        app.config['CHAT_HISTORY_ACTIVE_LIMIT'] = 2

        # 1. Initially, create 4 messages (with limit 2, 2 older)
        messages_first = [
            ChatMessage(id=1, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg A'),
            ChatMessage(id=2, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg B'),
            ChatMessage(id=3, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg C'),
            ChatMessage(id=4, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg D'),
        ]

        with patch.object(ChatService, 'generate_summary', return_value="Summary A-B") as mock_summarize:
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages_first, locale='en') as ctx:
                assert ctx.summary == "Summary A-B"
                mock_summarize.assert_called_once()
                
            # Verify it's cached
            cached = cache.get(cache_key)
            assert cached is not None
            assert cached['summary'] == "Summary A-B"
            assert cached['last_msg_id'] == 2

        # 2. Subsequent call with same messages shouldn't call generate_summary again
        with patch.object(ChatService, 'generate_summary') as mock_summarize:
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages_first, locale='en') as ctx:
                assert ctx.summary == "Summary A-B"
                mock_summarize.assert_not_called()

        # 3. Add 2 more messages (now total 6, with limit 2, 4 older)
        # The new older messages are 3 and 4 (since 5 and 6 are active)
        messages_second = messages_first + [
            ChatMessage(id=5, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg E'),
            ChatMessage(id=6, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg F'),
        ]

        with patch.object(ChatService, 'generate_summary', return_value="Summary A-D") as mock_summarize:
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages_second, locale='en') as ctx:
                assert ctx.summary == "Summary A-D"
                # Check that it passed "Summary A-B" as previous summary and only Msg C, D as new text
                mock_summarize.assert_called_once()
                args, kwargs = mock_summarize.call_args
                assert args[0] == "Summary A-B"
                assert "Msg C" in args[1]
                assert "Msg D" in args[1]
                assert "Msg A" not in args[1]
                
            # Check cached update
            cached = cache.get(cache_key)
            assert cached['summary'] == "Summary A-D"
            assert cached['last_msg_id'] == 4

def test_character_ceilings(app, staff_user, default_club):
    """Test that database context and summary ceilings are applied correctly."""
    with app.app_context():
        app.config['CHAT_HISTORY_ACTIVE_LIMIT'] = 1

        messages = [
            ChatMessage(id=1, user_id=staff_user.id, club_id=default_club.id, role='user', content='Msg A'),
            ChatMessage(id=2, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Msg B'),
        ]

        long_summary = "A" * 5000
        long_db_context = "[Database Context for Current Query]\n" + "B" * 4000

        with patch.object(ChatService, 'generate_summary', return_value=long_summary), \
             patch.object(ChatService, 'get_query_context', return_value=long_db_context):
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages, locale='en') as ctx:
                # Summary ceiling is 4000 chars
                assert "[Summary of older conversation in this session]" in ctx.system_prompt
                assert len(ctx.summary) == 5000  # summary variable stores raw summary
                # Check that system prompt portion is truncated to 4000
                assert "A" * 4000 in ctx.system_prompt
                assert "A" * 4001 not in ctx.system_prompt
                
                # DB Context ceiling is 3000 chars
                assert "[Database Context for Current Query]" in ctx.system_prompt
                assert "B" * 2500 in ctx.system_prompt
                assert "[Context truncated due to size limit...]" in ctx.system_prompt

def test_clear_chat_evicts_cache(app, client, auth, staff_user, default_club):
    """Test that clearing chat history also evicts the cached summary context."""
    cache_key = f"chat_summary_{staff_user.id}_{default_club.id}"
    
    with app.app_context():
        # Set cache
        cache.set(cache_key, {'summary': 'Cached Summary', 'last_msg_id': 1})
        assert cache.get(cache_key) is not None

    # Log in
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)

    # Call clear chat route
    response = client.post('/chat/clear')
    assert response.status_code == 200
    
    # Check cache is evicted
    with app.app_context():
        assert cache.get(cache_key) is None

def test_failed_db_turn_filtering(app, staff_user, default_club):
    """Test that turns where tools were enforced but not called (failed/hallucinated) are excluded."""
    with app.app_context():
        app.config['CHAT_HISTORY_ACTIVE_LIMIT'] = 20
        messages = [
            # Turn 1: Conversational (should keep)
            ChatMessage(id=1, user_id=staff_user.id, club_id=default_club.id, role='user', content='Hello'),
            ChatMessage(id=2, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='Hello back!'),
            # Turn 2: Database request that executed tools (should keep)
            ChatMessage(id=3, user_id=staff_user.id, club_id=default_club.id, role='user', content='assign role timer to John'),
            ChatMessage(
                id=4, user_id=staff_user.id, club_id=default_club.id, role='assistant', 
                content='Successfully assigned role.', tool_calls='[{"id": "call_1", "name": "assign_role", "arguments": {}, "result": {}}]'
            ),
            # Turn 3: Database request that bypassed tools (should filter out)
            ChatMessage(id=5, user_id=staff_user.id, club_id=default_club.id, role='user', content='assign role timer to John'),
            ChatMessage(id=6, user_id=staff_user.id, club_id=default_club.id, role='assistant', content='I hallucinated this text success!', tool_calls=None),
            # Current Message: (should keep)
            ChatMessage(id=7, user_id=staff_user.id, club_id=default_club.id, role='user', content='Next user request')
        ]

        with patch.object(ChatService, 'generate_summary', return_value="Mock summary") as mock_summarize:
            with ChatHistoryContext(staff_user, default_club.id, chat_history_list=messages, locale='en') as ctx:
                print("\nALL MESSAGES in CTX:", ctx.messages)
                active_contents = [m['content'] for m in ctx.messages if isinstance(m['content'], str)]
                print("ACTIVE CONTENTS:", active_contents)
                assert 'Next user request' in active_contents
                assert 'Hello' in active_contents

