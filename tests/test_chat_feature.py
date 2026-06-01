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
    """Test the command parser help response."""
    from app.services.command_parser import CommandParser
    with app.app_context():
        success, reply = CommandParser.parse_and_execute('/help', staff_user, 1)
        assert success is True
        assert 'Available Chat Commands' in reply

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



