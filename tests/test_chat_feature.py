import pytest
from app import db
from app.models import ChatMessage, Permission, AuthRole as Role, Contact, Meeting, SessionType, MeetingRole, SessionLog
from app.auth.permissions import Permissions
import json

@pytest.fixture
def chat_permissions(app):
    """Seed chat permissions for testing."""
    with app.app_context():
        # Ensure permissions exist
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        if not cmd_perm:
            cmd_perm = Permission(name=Permissions.CHAT_COMMANDS, description="Chat commands", category="Chat")
            db.session.add(cmd_perm)
            
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        if not ai_perm:
            ai_perm = Permission(name=Permissions.CHAT_AI, description="Chat AI", category="Chat")
            db.session.add(ai_perm)
            
        db.session.commit()
    return cmd_perm, ai_perm

def test_chat_access_denied_by_default(client, auth, staff_user, default_club):
    """Users without chat permissions should get a 403 Forbidden."""
    # Log in first
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)
    
    # Test send
    response = client.post('/chat/send', json={'message': '/help'})
    assert response.status_code == 403
    
    # Test history
    response = client.get('/chat/history')
    assert response.status_code == 403

def test_chat_access_granted_with_permission(client, auth, staff_user, default_club, chat_permissions, app):
    """Users with CHAT_COMMANDS or CHAT_AI permission should access chat routes."""
    # Grant CHAT_COMMANDS permission to the logged in user's role
    with app.app_context():
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        if cmd_perm not in role.permissions:
            role.permissions.append(cmd_perm)
        db.session.commit()
        
    # Log in
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)
    
    # Test send (Command Mode)
    response = client.post('/chat/send', json={'message': '/help'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['mode'] == 'command'
    assert 'Available Chat Commands' in data['content']
    
    # Test history
    response = client.get('/chat/history')
    assert response.status_code == 200
    history_data = response.get_json()
    assert history_data['success'] is True
    # User message and Assistant response
    assert len(history_data['messages']) >= 2

def test_command_parser_help(app, staff_user):
    """Test the command parser help response with and without permissions."""
    from app.services.command_parser import CommandParser
    from app.models import Permission, AuthRole as Role
    from app.auth.permissions import Permissions
    with app.app_context():
        # 1. Without meeting view permissions: meeting commands should be hidden
        success, reply = CommandParser.parse_and_execute('/help', staff_user, 1)
        assert success is True
        assert 'Available Chat Commands' in reply
        assert '/search' in reply
        assert '/query-pathways' in reply
        assert '/meeting-info' not in reply
        assert '<meeting_number>' not in reply
        assert '<meeting_id>' not in reply

        # 2. Grant meeting view permission: meeting commands should now show up
        role = Role.query.filter_by(name='Staff').first()
        agenda_perm = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        if agenda_perm not in role.permissions:
            role.permissions.append(agenda_perm)
            db.session.commit()

        success, reply = CommandParser.parse_and_execute('/help', staff_user, 1)
        assert success is True
        assert 'Available Chat Commands' in reply
        assert '/meeting-info' in reply
        assert '<meeting_number>' in reply
        assert '<meeting_id>' not in reply

def test_command_parser_invalid_command(app, staff_user):
    """Test how command parser handles invalid formats."""
    from app.services.command_parser import CommandParser
    with app.app_context():
        success, reply = CommandParser.parse_and_execute('hello', staff_user, 1)
        assert success is False
        assert 'Invalid command format' in reply
        
        success, reply = CommandParser.parse_and_execute('/invalidcmd', staff_user, 1)
        assert success is False
        assert "Unknown command" in reply

def test_chat_service_prompt(app, staff_user, default_club):
    """Test ChatService system prompt generation to ensure imports and queries work."""
    from app.services.chat_service import ChatService
    with app.app_context():
        prompt = ChatService.get_system_prompt(staff_user, default_club.id, 'en')
        assert "AI Assistant" in prompt
        assert default_club.club_name in prompt

def test_should_enforce_tools(app):
    """Test tool enforcement classifier triggers for English and Chinese queries."""
    from app.services.chat_service import ChatService
    with app.app_context():
        # Things that SHOULD trigger tool enforcement
        assert ChatService.should_enforce_tools("show me the voting results of meeting 973") is True
        assert ChatService.should_enforce_tools("who is Vijay Vasant?") is True
        assert ChatService.should_enforce_tools("assign TME role to Bing Zhang") is True
        assert ChatService.should_enforce_tools("meeting 975 results") is True
        assert ChatService.should_enforce_tools("会议 973 结果") is True
        assert ChatService.should_enforce_tools("指派 TME 角色给 Bing") is True
        assert ChatService.should_enforce_tools("What's the status of meeting 173?") is True
        
        # Things that SHOULD NOT trigger tool enforcement (conversational)
        assert ChatService.should_enforce_tools("Hello") is False
        assert ChatService.should_enforce_tools("hi") is False
        assert ChatService.should_enforce_tools("thanks") is False
        assert ChatService.should_enforce_tools("who are you") is False
        assert ChatService.should_enforce_tools("help") is False

def test_get_query_context(app, default_club):
    """Test dynamic query context generation from database."""
    from app.services.chat_service import ChatService
    from app.models import Contact, ContactClub, Meeting
    from datetime import date
    with app.app_context():
        # Create a test contact and meeting for verification
        test_contact = Contact(Name="John Doe Test", Type="Member", Email="john@test.com")
        db.session.add(test_contact)
        db.session.flush()
        
        cc = ContactClub(contact_id=test_contact.id, club_id=default_club.id)
        db.session.add(cc)
        
        test_meeting = Meeting(club_id=default_club.id, Meeting_Number=888, Meeting_Date=date.today(), status="not started")
        db.session.add(test_meeting)
        db.session.commit()
        
        try:
            # Test contact search context
            ctx = ChatService.get_query_context("who is John Doe?", default_club.id)
            assert "Contact in directory: Name='John Doe Test'" in ctx
            assert "ID:" in ctx
            
            # Test meeting search context
            ctx = ChatService.get_query_context("meeting 888 details", default_club.id)
            assert "Meeting #888 exists" in ctx
            assert "Date:" in ctx
            
            # Test upcoming meetings context
            ctx = ChatService.get_query_context("what is the upcoming meeting?", default_club.id)
            assert "Upcoming/Active Meeting #888" in ctx
        finally:
            # Clean up
            db.session.delete(cc)
            db.session.delete(test_contact)
            db.session.delete(test_meeting)
            db.session.commit()


def test_tool_get_meeting_agenda(app, default_club, staff_user):
    """Test retrieving meeting agenda via ChatToolExecutor."""
    from app.services.chat_tool_executor import ChatToolExecutor
    from app.models import Meeting, SessionLog, SessionType, Contact, AuthRole as Role, Permission
    from app.auth.permissions import Permissions
    from datetime import date, time
    with app.app_context():
        # Ensure AGENDA_VIEW permission exists and is granted to Staff role
        role = Role.query.filter_by(name='Staff').first()
        agenda_perm = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        if not agenda_perm:
            agenda_perm = Permission(name=Permissions.AGENDA_VIEW, description="View agenda", category="Agenda")
            db.session.add(agenda_perm)
            db.session.flush()
        if agenda_perm not in role.permissions:
            role.permissions.append(agenda_perm)
        db.session.commit()

        # Create a test meeting and agenda
        test_meeting = Meeting(club_id=default_club.id, Meeting_Number=999, Meeting_Date=date.today(), status="not started")
        db.session.add(test_meeting)
        db.session.flush()
        
        # Ensure a SessionType exists or create one
        st = SessionType.query.filter_by(Title="Prepared Speech").first()
        if not st:
            st = SessionType(Title="Prepared Speech", Duration_Min=5, Duration_Max=7)
            db.session.add(st)
            db.session.flush()
            
        test_owner = Contact(Name="Agenda Owner Test", Type="Member")
        db.session.add(test_owner)
        db.session.flush()
        
        log = SessionLog(
            meeting_id=test_meeting.id,
            Meeting_Seq=1,
            Session_Title="Custom Speech",
            Type_ID=st.id,
            Start_Time=time(19, 15, 0),
            state="active"
        )
        db.session.add(log)
        db.session.flush()
        
        # Set owner (needs junction table)
        log.owners = [test_owner.id]
        db.session.commit()
        
        try:
            with app.test_request_context():
                from flask_login import login_user
                from flask import session
                session['current_club_id'] = default_club.id
                login_user(staff_user)
                # Execute tool
                params = {'meeting_identifier': '999'}
                res = ChatToolExecutor.execute('get_meeting_agenda', params, staff_user, default_club.id)
                assert res['success'] is True
                assert "Meeting #999 Agenda" in res['message']
                assert "19:15" in res['message']
                assert "Custom Speech" in res['message']
                assert "Agenda Owner Test" in res['message']
        finally:
            # Clean up
            # Clear junction table first
            from app.models import OwnerMeetingRoles
            OwnerMeetingRoles.query.filter_by(meeting_id=test_meeting.id).delete()
            db.session.delete(log)
            db.session.delete(test_owner)
            db.session.delete(test_meeting)
            db.session.commit()


def test_route_interception_winners_and_agenda(client, auth, staff_user, default_club, chat_permissions, app):
    """Test router-level regex interception for winners and agendas."""
    # Grant permissions
    with app.app_context():
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        agenda_perm = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        voting_perm = Permission.query.filter_by(name=Permissions.VOTING_VIEW_RESULTS).first()
        
        # Ensure voting permission exists
        if not voting_perm:
            voting_perm = Permission(name=Permissions.VOTING_VIEW_RESULTS, description="View voting", category="Voting")
            db.session.add(voting_perm)
            db.session.flush()
            
        for p in [cmd_perm, ai_perm, agenda_perm, voting_perm]:
            if p not in role.permissions:
                role.permissions.append(p)
        db.session.commit()

    # Log in
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)

    with app.app_context():
        # Create a test meeting with number 777
        from datetime import date
        test_meeting = Meeting(club_id=default_club.id, Meeting_Number=777, Meeting_Date=date.today(), status="finished")
        db.session.add(test_meeting)
        db.session.commit()

    try:
        # 1. Test Winners Interception
        response = client.post('/chat/send', json={'message': 'who are the winners of meeting 777'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'Voting results for **Meeting #777**' in data['content']
        assert data['executed_tools'][0]['name'] == 'get_voting_results'
        
        # 2. Test Agenda Interception
        response = client.post('/chat/send', json={'message': 'show me the agenda of 777'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'agenda for Meeting #777' in data['content']
        assert data['executed_tools'][0]['name'] == 'get_meeting_agenda'
    finally:
        with app.app_context():
            Meeting.query.filter_by(Meeting_Number=777).delete()
            db.session.commit()


def test_tools_guidelines_loading_and_injection(app):
    """Test loading, caching, and dynamic injection of tools guidelines."""
    from app.services.chat_service import ChatService
    with app.app_context():
        # Clear cache first to force reload
        ChatService._tools_guidelines = None
        
        # 1. Test loader method
        guidelines = ChatService.get_tools_guidelines()
        assert guidelines is not None
        assert "Chatbot Tool Guidelines & Constraints" in guidelines
        assert "No Database Hallucinations" in guidelines
        assert "Linear Progression" in guidelines
        
        # 2. Test cache works
        guidelines_again = ChatService.get_tools_guidelines()
        assert guidelines_again is guidelines
        
        # 3. Test dynamic injection in process_chat_completion logic
        from unittest.mock import MagicMock, patch
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.stop_reason = "text"
        mock_response.content = [MagicMock(type="text", text="Mock reply")]
        mock_client.messages.create.return_value = mock_response
        
        from app.models import ChatMessage
        mock_user = MagicMock()
        mock_user.username = "test_user"
        mock_user.id = 1
        
        mock_user.get_contact = MagicMock(return_value=None)
        mock_user.primary_role_name = "Member"
        
        chat_msg = ChatMessage(role="user", content="show me the meeting agenda details")
        
        with patch.object(ChatService, 'get_client', return_value=mock_client), \
             patch('app.services.chat_service.db.session.get', return_value=None), \
             patch('app.services.chat_service.current_app.config.get', side_effect=lambda k, d=None: d if k != 'ANTHROPIC_API_KEY' else 'mock-api-key'):
            
            reply, executed = ChatService.process_chat_completion(
                chat_history_list=[chat_msg],
                user=mock_user,
                club_id=1,
                locale="en"
            )
            
            assert reply == "Mock reply"
            
            # Verify system prompt passed to client.messages.create contains guidelines
            call_kwargs = mock_client.messages.create.call_args[1]
            system_prompt = call_kwargs.get('system', '')
            assert "Chatbot Tool Guidelines & Constraints" in system_prompt
            assert "No Database Hallucinations" in system_prompt


def test_chat_assistant_language_toggle(app, client, auth, staff_user, default_club, chat_permissions):
    """Test that toggling language changes the AI prompt, system reminders, and intercepted tool outputs."""
    from app.services.chat_service import ChatService
    from unittest.mock import MagicMock, patch
    
    with app.app_context():
        # 1. Test get_system_prompt instructions
        prompt_en = ChatService.get_system_prompt(staff_user, default_club.id, 'en')
        assert "if 'zh_CN', you must always respond in Chinese" in prompt_en
        assert "User Locale: en" in prompt_en

        prompt_zh = ChatService.get_system_prompt(staff_user, default_club.id, 'zh_CN')
        assert "if 'zh_CN', you must always respond in Chinese" in prompt_zh
        assert "User Locale: zh_CN" in prompt_zh

        # 2. Test language reminder injection in process_chat_completion
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.stop_reason = "text"
        mock_response.content = [MagicMock(type="text", text="Mock reply")]
        mock_client.messages.create.return_value = mock_response
        
        chat_msg = ChatMessage(role="user", content="hello")
        
        with patch.object(ChatService, 'get_client', return_value=mock_client), \
             patch('app.services.chat_service.db.session.get', return_value=None), \
             patch('app.services.chat_service.current_app.config.get', side_effect=lambda k, d=None: d if k != 'ANTHROPIC_API_KEY' else 'mock-api-key'):
            
            # Locale en
            ChatService.process_chat_completion(
                chat_history_list=[chat_msg],
                user=staff_user,
                club_id=default_club.id,
                locale="en"
            )
            call_kwargs_en = mock_client.messages.create.call_args[1]
            last_msg_en = call_kwargs_en.get('messages', [])[-1]['content']
            assert "Remember, you must respond in English because the User Locale is 'en'." in last_msg_en

            # Locale zh_CN
            ChatService.process_chat_completion(
                chat_history_list=[chat_msg],
                user=staff_user,
                club_id=default_club.id,
                locale="zh_CN"
            )
            call_kwargs_zh = mock_client.messages.create.call_args[1]
            last_msg_zh = call_kwargs_zh.get('messages', [])[-1]['content']
            assert "Remember, you must respond in Chinese because the User Locale is 'zh_CN'." in last_msg_zh

    # Grant permissions for intercepts
    with app.app_context():
        from app.models import AuthRole as Role, Permission
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        agenda_perm = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        voting_perm = Permission.query.filter_by(name=Permissions.VOTING_VIEW_RESULTS).first()
        for p in [cmd_perm, ai_perm, agenda_perm, voting_perm]:
            if p not in role.permissions:
                role.permissions.append(p)
        db.session.commit()

        # Create a finished test meeting
        from datetime import date
        test_meeting = Meeting(club_id=default_club.id, Meeting_Number=555, Meeting_Date=date.today(), status="finished")
        db.session.add(test_meeting)
        db.session.commit()

    try:
        # Log in
        auth.login(username=staff_user.username, password='password', club_id=default_club.id)

        # 3. Test intercepted agenda outputs with locale zh_CN vs en
        with client.session_transaction() as sess:
            sess['locale'] = 'zh_CN'
        response = client.post('/chat/send', json={'message': 'show me the agenda of 555'})
        assert response.status_code == 200
        data = response.get_json()
        assert "会议 #555" in data['content']
        assert "日程表暂无内容" in data['content']

        with client.session_transaction() as sess:
            sess['locale'] = 'en'
        response = client.post('/chat/send', json={'message': 'show me the agenda of 555'})
        assert response.status_code == 200
        data = response.get_json()
        assert "agenda for Meeting #555" in data['content']

        # 4. Test intercepted voting outputs with locale zh_CN vs en
        with client.session_transaction() as sess:
            sess['locale'] = 'zh_CN'
        response = client.post('/chat/send', json={'message': 'who are the winners of meeting 555'})
        assert response.status_code == 200
        data = response.get_json()
        assert "会议 **#555** 的投票结果" in data['content']

        with client.session_transaction() as sess:
            sess['locale'] = 'en'
        response = client.post('/chat/send', json={'message': 'who are the winners of meeting 555'})
        assert response.status_code == 200
        data = response.get_json()
        assert "Voting results for **Meeting #555**" in data['content']

    finally:
        with app.app_context():
            Meeting.query.filter_by(Meeting_Number=555).delete()
            db.session.commit()


def test_slash_command_in_ai_mode_with_permission(client, auth, staff_user, default_club, chat_permissions, app):
    """Test that slash command in AI mode works if the user has CHAT_COMMANDS permission."""
    # Grant both CHAT_AI and CHAT_COMMANDS permissions to the user's role
    with app.app_context():
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        if cmd_perm not in role.permissions:
            role.permissions.append(cmd_perm)
        if ai_perm not in role.permissions:
            role.permissions.append(ai_perm)
        db.session.commit()

    # Log in
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)

    # Test slash command in AI mode
    response = client.post('/chat/send', json={'message': '/help'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['mode'] == 'ai'
    assert 'Available Chat Commands' in data['content']


def test_slash_command_in_ai_mode_without_permission(client, auth, staff_user, default_club, chat_permissions, app):
    """Test that slash command in AI mode returns 403 if the user does NOT have CHAT_COMMANDS permission."""
    # Grant CHAT_AI but revoke CHAT_COMMANDS
    with app.app_context():
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        if cmd_perm in role.permissions:
            role.permissions.remove(cmd_perm)
        if ai_perm not in role.permissions:
            role.permissions.append(ai_perm)
        db.session.commit()

    # Log in
    auth.login(username=staff_user.username, password='password', club_id=default_club.id)

    # Test slash command in AI mode
    response = client.post('/chat/send', json={'message': '/help'})
    assert response.status_code == 403
    data = response.get_json()
    assert data['success'] is False
    assert 'Permission denied' in data['message']


def test_slash_command_status_query(client, auth, staff_user, default_club, chat_permissions, app):
    """Test that /status <meeting_number> acts as a query when status is omitted."""
    # Ensure CHAT_COMMANDS & AGENDA_EDIT permission
    with app.app_context():
        role = Role.query.filter_by(name='Staff').first()
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        agenda_perm = Permission.query.filter_by(name=Permissions.AGENDA_EDIT).first()
        if cmd_perm not in role.permissions:
            role.permissions.append(cmd_perm)
        if agenda_perm not in role.permissions:
            role.permissions.append(agenda_perm)
        db.session.commit()

        # Create a test meeting
        from datetime import date
        test_meeting = Meeting(club_id=default_club.id, Meeting_Number=666, Meeting_Date=date.today(), status="not started")
        db.session.add(test_meeting)
        db.session.commit()

    try:
        # Log in
        auth.login(username=staff_user.username, password='password', club_id=default_club.id)

        # 1. Query status
        response = client.post('/chat/send', json={'message': '/status 666'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert "Meeting #666 status is `not started`" in data['content']

        # 2. Update status
        response = client.post('/chat/send', json={'message': '/status 666 running'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # 3. Query status again to verify update
        response = client.post('/chat/send', json={'message': '/status 666'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert "Meeting #666 status is `running`" in data['content']
    finally:
        with app.app_context():
            Meeting.query.filter_by(Meeting_Number=666).delete()
            db.session.commit()









