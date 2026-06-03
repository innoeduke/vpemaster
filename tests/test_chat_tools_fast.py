import sys
import os
import pytest
from datetime import date, time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))

from app import db
from app.models import (
    Club, Contact, User, AuthRole, Permission, Meeting, SessionType,
    SessionLog, Pathway, Ticket, ChatMessage, ContactClub, UserClub,
    MeetingRole
)
from sqlalchemy import func
from app.auth.permissions import Permissions
from app.services.chat_service import ChatService
from app.services.chat_tool_executor import ChatToolExecutor

# --- Mocking Utilities ---

class MockBlock:
    def __init__(self, type_name, **kwargs):
        self.type = type_name
        for k, v in kwargs.items():
            setattr(self, k, v)

def make_tool_response(tool_name, tool_input, call_id="call_1"):
    block = MockBlock("tool_use", id=call_id, name=tool_name, input=tool_input)
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response

def make_text_response(text_content):
    block = MockBlock("text", text=text_content)
    response = MagicMock()
    response.stop_reason = "text"
    response.content = [block]
    return response

def mock_llm_chain(responses_list):
    """
    Patches ChatService.get_client to return a mock client whose messages.create
    method yields the objects in responses_list sequentially.
    """
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses_list
    return patch('app.services.chat_service.ChatService.get_client', return_value=mock_client)


# --- Setup Fixture (In Memory SQLite) ---

@pytest.fixture(scope='function')
def setup_ai_environment(app):
    """Seed the database with all necessary components for AI tool testing."""
    with app.app_context():
        # 1. Clean existing tables to prevent conflicts
        db.drop_all()
        db.create_all()
        AuthRole.clear_role_cache()

        # 2. Grant all permissions
        perms_to_seed = []
        seen_names = set()
        for attr in dir(Permissions):
            if attr.isupper() and not attr.startswith('_'):
                name = getattr(Permissions, attr)
                if attr in ['SYSADMIN', 'CLUBADMIN', 'STAFF', 'USER']:
                    continue
                if name in seen_names:
                    continue
                seen_names.add(name)
                perm = Permission.query.filter_by(name=name).first()
                if not perm:
                    perm = Permission(name=name, category='chat_test')
                    perms_to_seed.append(perm)
        if perms_to_seed:
            db.session.add_all(perms_to_seed)
            db.session.flush()

        # Create/Get Staff role
        role = AuthRole.query.filter_by(name='Staff').first()
        if not role:
            role = AuthRole(name='Staff', level=2)
            db.session.add(role)
            db.session.flush()

        # Associate all permissions to Staff role
        all_perms = Permission.query.all()
        for p in all_perms:
            if p not in role.permissions:
                role.permissions.append(p)
        db.session.flush()

        # 3. Create test Club
        club = Club(
            club_no='000001',
            club_name='Shanghai Leadership Toastmasters Club',
            district='85',
            division='A',
            area='1'
        )
        db.session.add(club)
        db.session.flush()

        # 4. Create contacts
        john = Contact(
            Name='John Doe',
            Type='Member',
            Email='john.doe@example.com',
            Phone_Number='13800000001',
            Date_Created=date.today()
        )
        alice = Contact(
            Name='Alice Johnson',
            Type='Guest',
            Email='alice.j@example.com',
            Phone_Number='13912345678',
            Date_Created=date.today()
        )
        db.session.add_all([john, alice])
        db.session.flush()

        # 5. Link contacts to club
        cc_john = ContactClub(contact_id=john.id, club_id=club.id, is_officer=False)
        cc_alice = ContactClub(contact_id=alice.id, club_id=club.id, is_officer=False)
        db.session.add_all([cc_john, cc_alice])
        db.session.flush()

        # 6. Create User and link to John Doe
        user = User(
            username='johndoe',
            email='john.doe@example.com',
            status='active'
        )
        user.set_password('password')
        user.roles.append(role)
        db.session.add(user)
        db.session.flush()

        uc = UserClub(
            user_id=user.id,
            club_id=club.id,
            contact_id=john.id,
            club_role_level=role.level
        )
        db.session.add(uc)
        db.session.flush()

        # 7. Create tickets for roster check-ins
        t1 = Ticket(name='Officer', type='Officer', price=0, club_id=club.id)
        t2 = Ticket(name='Early-bird', type='Member', price=0, club_id=club.id)
        t3 = Ticket(name='Walk-in', type='Guest', price=40, club_id=club.id)
        db.session.add_all([t1, t2, t3])
        db.session.flush()

        # 8. Create Pathways
        path1 = Pathway(name='Dynamic Leadership', abbr='DL', status='active', type='pathway')
        path2 = Pathway(name='Presentation Mastery', abbr='PM', status='active', type='pathway')
        db.session.add_all([path1, path2])
        db.session.flush()

        # 9. Create a SessionType for Role bookings
        st = SessionType(Title='Prepared Speech', Duration_Min=5, Duration_Max=7)
        db.session.add(st)
        db.session.flush()

        # 10. Create meeting role "Prepared Speaker"
        mr = MeetingRole(name='Prepared Speaker', type='Speech', needs_approval=False, has_single_owner=True)
        db.session.add(mr)
        db.session.flush()
        
        # Link role to SessionType
        st.role_id = mr.id
        db.session.flush()

        # 11. Create Meeting #100
        meeting = Meeting(
            club_id=club.id,
            Meeting_Number=100,
            Meeting_Date=date(2026, 6, 15),
            Meeting_Title='Shanghai Leadership Meeting #100',
            Start_Time=time(19, 0, 0),
            status='not started',
            type='Keynote Speech'
        )
        db.session.add(meeting)
        db.session.flush()

        # 12. Create SessionLog
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Session_Title='Speech 1',
            Type_ID=st.id,
            Start_Time=time(19, 15, 0),
            state='active'
        )
        db.session.add(log)
        db.session.commit()

        env_data = {
            'club_id': club.id,
            'user_id': user.id,
            'john_id': john.id,
            'alice_id': alice.id,
            'meeting_id': meeting.id,
            'log_id': log.id
        }
        
        with app.test_request_context():
            from flask import session
            from flask_login import login_user
            session['current_club_id'] = club.id
            login_user(user)
            yield env_data


# --- Fast Test Implementations ---

def test_fast_ai_create_meeting(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Please create a new meeting on 2026-07-01 using the template 'Speech Contest'.",
            mode='ai'
        )
        
        r1 = make_tool_response('create_meeting', {'date': '2026-07-01', 'template_name': 'Speech Contest'})
        r2 = make_text_response("Successfully created Meeting #101!")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'create_meeting'
        assert tool_call['arguments']['date'] == '2026-07-01'
        assert '101' in reply_text


def test_fast_ai_assign_role(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Assign John Doe to the role of Prepared Speaker for meeting 100.",
            mode='ai'
        )
        
        r1 = make_tool_response('manage_meeting_roles', {'action': 'assign', 'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'})
        r2 = make_text_response("Successfully assigned John Doe as Prepared Speaker.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'manage_meeting_roles'
        assert tool_call['arguments']['action'] == 'assign'
        assert tool_call['arguments']['meeting_identifier'] == '100'


def test_fast_ai_cancel_role(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        
        # Pre-assign John Doe so cancel works
        ChatToolExecutor.tool_manage_meeting_roles(
            {'action': 'assign', 'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'},
            user, env['club_id']
        )
        db.session.commit()

        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Can you cancel John Doe's Prepared Speaker role for meeting 100?",
            mode='ai'
        )
        
        r1 = make_tool_response('manage_meeting_roles', {'action': 'cancel', 'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'})
        r2 = make_text_response("Successfully cancelled assignment.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'manage_meeting_roles'
        assert tool_call['arguments']['action'] == 'cancel'


def test_fast_ai_add_contact(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Add a new guest contact named Bob Smith with email bob@example.com and phone 13511112222.",
            mode='ai'
        )
        
        r1 = make_tool_response('add_contact', {'name': 'Bob Smith', 'email': 'bob@example.com', 'phone': '13511112222'})
        r2 = make_text_response("Successfully created guest contact Bob Smith.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'add_contact'
        assert tool_call['arguments']['name'] == 'Bob Smith'


def test_fast_ai_check_in(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Please check in Alice Johnson for meeting 100.",
            mode='ai'
        )
        
        r1 = make_tool_response('check_in', {'meeting_identifier': '100', 'contact_name': 'Alice Johnson'})
        r2 = make_text_response("Successfully checked in Alice Johnson.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'check_in'
        assert tool_call['arguments']['meeting_identifier'] == '100'


def test_fast_ai_complete_level(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Record Level 2 completion in Dynamic Leadership for John Doe.",
            mode='ai'
        )
        
        r1 = make_tool_response('complete_level', {'contact_name': 'John Doe', 'pathway_name': 'Dynamic Leadership', 'level': 2})
        r2 = make_text_response("Successfully recorded achievement.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'complete_level'
        assert tool_call['arguments']['level'] == 2


def test_fast_ai_get_pathway_status(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show pathway status and achievements for John Doe.",
            mode='ai'
        )
        
        r1 = make_tool_response('get_pathway_status', {'contact_name': 'John Doe'})
        r2 = make_text_response("Dynamic Leadership (working)")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_pathway_status'


def test_fast_ai_search_contacts(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Search for contacts matching the name 'Alice'.",
            mode='ai'
        )
        
        r1 = make_tool_response('search_contacts', {'name': 'Alice'})
        r2 = make_text_response("Found Alice Johnson.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'search_contacts'


def test_fast_ai_get_meeting_info(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Get meeting details and theme for meeting #100.",
            mode='ai'
        )
        
        r1 = make_tool_response('get_meeting_info', {'meeting_identifier': '100'})
        r2 = make_text_response("Meeting #100 theme is Keynote Speech.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_meeting_info'


def test_fast_ai_list_meetings(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Can you show me a list of meeting schedules?",
            mode='ai'
        )
        
        r1 = make_tool_response('list_meetings', {})
        r2 = make_text_response("Meeting list...")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'list_meetings'


def test_fast_ai_get_role_assignments(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Who is assigned to roles for meeting 100?",
            mode='ai'
        )
        
        r1 = make_tool_response('manage_meeting_roles', {'action': 'query', 'meeting_identifier': '100'})
        r2 = make_text_response("Roles list...")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'manage_meeting_roles'
        assert tool_call['arguments']['action'] == 'query'


def test_fast_ai_get_available_roles(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me all vacant or unassigned roles for meeting 100.",
            mode='ai'
        )
        
        r1 = make_tool_response('manage_meeting_roles', {'action': 'query_available', 'meeting_identifier': '100'})
        r2 = make_text_response("Available roles...")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'manage_meeting_roles'
        assert tool_call['arguments']['action'] == 'query_available'


def test_fast_ai_update_meeting_status(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Update meeting 100 status to finished.",
            mode='ai'
        )
        
        r1 = make_tool_response('update_meeting_status', {'meeting_identifier': '100', 'status': 'finished'})
        r2 = make_text_response("Meeting status updated.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'update_meeting_status'


def test_fast_ai_get_voting_results(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Get voting results and awards details of meeting 100.",
            mode='ai'
        )
        
        r1 = make_tool_response('get_voting_results', {'meeting_identifier': '100'})
        r2 = make_text_response("Winners list...")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_voting_results'


def test_fast_ai_get_meeting_agenda(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me the sequence of events and agenda for meeting #100.",
            mode='ai'
        )
        
        r1 = make_tool_response('get_meeting_agenda', {'meeting_identifier': '100'})
        r2 = make_text_response("Meeting agenda sequence...")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_meeting_agenda'


def test_fast_ai_start_meeting(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="start meeting 100",
            mode='ai'
        )
        
        r1 = make_tool_response('update_meeting_status', {'meeting_identifier': '100', 'status': 'running'})
        r2 = make_text_response("Meeting #100 started successfully.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'update_meeting_status'
        assert tool_call['arguments']['status'] == 'running'


def test_fast_ai_finish_unstarted_meeting_fails(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="finish meeting 100",
            mode='ai'
        )
        
        r1 = make_tool_response('update_meeting_status', {'meeting_identifier': '100', 'status': 'finished'})
        r2 = make_text_response("Cannot finish the meeting. Meeting #100 is not started yet. You must start the meeting first.")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'update_meeting_status'
        assert tool_call['arguments']['status'] == 'finished'
        assert "not started" in reply_text.lower()


def test_fast_ai_query_pathways_library(app, setup_ai_environment):
    env = setup_ai_environment
    with app.app_context():
        # Register a pathway project for querying
        from app.models import Project, PathwayProject
        proj = Project(
            Project_Name="Test Speech Project",
            Format="Prepared Speech",
            Duration_Min=5,
            Duration_Max=7,
            Purpose="Test purpose"
        )
        db.session.add(proj)
        db.session.flush()

        pp = PathwayProject(
            path_id=1,
            project_id=proj.id,
            code="L1P1",
            level=1,
            type="required"
        )
        db.session.add(pp)
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me all the pathways in the library.",
            mode='ai'
        )
        
        r1 = make_tool_response('query_pathways_library', {})
        r2 = make_text_response("Dynamic Leadership")
        
        with mock_llm_chain([r1, r2]):
            reply_text, executed_tools = ChatService.process_chat_completion(
                chat_history_list=[msg],
                user=user,
                club_id=env['club_id'],
                locale='en'
            )
            
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'query_pathways_library'
