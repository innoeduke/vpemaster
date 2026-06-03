import sys
import os
import pytest
from datetime import date, time

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

@pytest.fixture(scope='function')
def setup_ai_environment(app):
    """Seed the database with all necessary components for AI tool testing."""
    with app.app_context():
        # 1. Clean existing tables to prevent conflicts
        db.drop_all()
        db.create_all()
        AuthRole.clear_role_cache()

        # 2. Grant all permissions
        # Seed permissions
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
        # Contact 1: John Doe (Member, linked to user account)
        john = Contact(
            Name='John Doe',
            Type='Member',
            Email='john.doe@example.com',
            Phone_Number='13800000001',
            Date_Created=date.today()
        )
        # Contact 2: Alice Johnson (Guest)
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

        # Retrieve IDs for testing assertions
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


def test_ai_create_meeting(app, setup_ai_environment):
    """Test 'create_meeting' tool calling by model."""
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


def test_ai_assign_role(app, setup_ai_environment):
    """Test 'assign_role' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        assign_call = next((t for t in executed_tools if t['name'] == 'manage_meeting_roles' and t['arguments'].get('action') == 'assign'), None)
        assert assign_call is not None, f"Expected assign action but executed tools were: {executed_tools}"
        assert assign_call['arguments']['meeting_identifier'] == '100'
        assert 'john' in assign_call['arguments']['contact_name'].lower()
        assert 'speaker' in assign_call['arguments']['role_name'].lower()


def test_ai_cancel_role(app, setup_ai_environment):
    """Test 'cancel_role' tool calling by model."""
    env = setup_ai_environment
    with app.app_context():
        # First assign John Doe to role so cancel makes sense
        from app.services.chat_tool_executor import ChatToolExecutor
        ChatToolExecutor.tool_manage_meeting_roles(
            {'action': 'assign', 'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'},
            db.session.get(User, env['user_id']),
            env['club_id']
        )
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        msg = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Can you cancel John Doe's Prepared Speaker role for meeting 100?",
            mode='ai'
        )
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        cancel_call = next((t for t in executed_tools if t['name'] == 'manage_meeting_roles' and t['arguments'].get('action') == 'cancel'), None)
        assert cancel_call is not None, f"Expected cancel action but executed tools were: {executed_tools}"
        assert cancel_call['arguments']['meeting_identifier'] == '100'
        assert 'john' in cancel_call['arguments']['contact_name'].lower()
        assert 'speaker' in cancel_call['arguments']['role_name'].lower()


def test_ai_add_contact(app, setup_ai_environment):
    """Test 'add_contact' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'add_contact'
        assert 'bob' in tool_call['arguments']['name'].lower()
        assert tool_call['arguments']['email'] == 'bob@example.com'


def test_ai_check_in(app, setup_ai_environment):
    """Test 'check_in' tool calling by model."""
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
        assert 'alice' in tool_call['arguments']['contact_name'].lower()


def test_ai_complete_level(app, setup_ai_environment):
    """Test 'complete_level' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'complete_level'
        assert 'john' in tool_call['arguments']['contact_name'].lower()
        assert 'dynamic' in tool_call['arguments']['pathway_name'].lower()
        assert int(tool_call['arguments']['level']) == 2


def test_ai_get_pathway_status(app, setup_ai_environment):
    """Test 'get_pathway_status' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_pathway_status'
        assert 'john' in tool_call['arguments']['contact_name'].lower()


def test_ai_search_contacts(app, setup_ai_environment):
    """Test 'search_contacts' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'search_contacts'
        assert 'alice' in tool_call['arguments']['name'].lower()


def test_ai_get_meeting_info(app, setup_ai_environment):
    """Test 'get_meeting_info' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_meeting_info'
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_list_meetings(app, setup_ai_environment):
    """Test 'list_meetings' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'list_meetings'


def test_ai_get_role_assignments(app, setup_ai_environment):
    """Test 'get_role_assignments' tool calling by model."""
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
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_get_available_roles(app, setup_ai_environment):
    """Test 'get_available_roles' tool calling by model."""
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
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_update_meeting_status(app, setup_ai_environment):
    """Test 'update_meeting_status' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = next((t for t in executed_tools if t['name'] == 'update_meeting_status' and t['arguments']['status'] == 'finished'), None)
        assert tool_call is not None
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_get_voting_results(app, setup_ai_environment):
    """Test 'get_voting_results' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = next((t for t in executed_tools if t['name'] == 'get_voting_results'), None)
        assert tool_call is not None
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_get_meeting_agenda(app, setup_ai_environment):
    """Test 'get_meeting_agenda' tool calling by model."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = next((t for t in executed_tools if t['name'] == 'get_meeting_agenda'), None)
        assert tool_call is not None
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']


def test_ai_start_meeting(app, setup_ai_environment):
    """Test starting a meeting using 'start meeting' command calls 'update_meeting_status' tool."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        assert len(executed_tools) > 0
        tool_call = next((t for t in executed_tools if t['name'] == 'update_meeting_status'), None)
        assert tool_call is not None, f"Expected update_meeting_status tool to be called, but got {executed_tools}"
        assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']
        assert tool_call['arguments']['status'] == 'running'


def test_ai_finish_unstarted_meeting_fails(app, setup_ai_environment):
    """Test that trying to finish an unstarted meeting fails due to linear progression and explains this to the user."""
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
        
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        
        tool_call = next((t for t in executed_tools if t['name'] == 'update_meeting_status' and t['arguments'].get('status') == 'finished'), None)
        if tool_call is not None:
            assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']
        # The reply text should contain educational info explaining linear progression or starting the meeting
        assert any(word in reply_text.lower() for word in ["not started", "linear", "start", "progression", "running"])


def test_ai_query_pathways_library(app, setup_ai_environment):
    """Test 'query_pathways_library' tool calling by model and correct response execution."""
    env = setup_ai_environment
    with app.app_context():
        from app.models import Project, PathwayProject
        proj = Project(
            Project_Name="Test Speech Project",
            Format="Prepared Speech",
            Duration_Min=5,
            Duration_Max=7,
            Purpose="Test purpose",
            Overview="Test overview",
            Requirements="Test requirements"
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
        
        # Test Case 1: Query pathways library general information
        msg1 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me all the pathways in the library.",
            mode='ai'
        )
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg1],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools) > 0
        assert executed_tools[0]['name'] == 'query_pathways_library'
        assert "Dynamic Leadership" in reply_text
        assert "Presentation Mastery" in reply_text

        # Test Case 2: Query specific project details
        msg2 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="What are the details of the 'Test Speech Project'?",
            mode='ai'
        )
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg2],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools) > 0
        assert executed_tools[0]['name'] == 'query_pathways_library'
        assert executed_tools[0]['arguments']['project_name'] == 'Test Speech Project'
        assert "Test Speech Project" in reply_text
        assert "Test purpose" in reply_text
        assert "Dynamic Leadership" in reply_text

        # Test Case 3: Query specific pathway and level
        msg3 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me level 1 projects under Dynamic Leadership.",
            mode='ai'
        )
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg3],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools) > 0
        assert executed_tools[0]['name'] == 'query_pathways_library'
        assert int(executed_tools[0]['arguments']['level']) == 1
        assert "Test Speech Project" in reply_text


def test_command_parser_query_pathways(app, setup_ai_environment):
    """Test '/query-pathways' CLI command parsing and execution."""
    env = setup_ai_environment
    with app.app_context():
        from app.models import Project, PathwayProject
        proj = Project(
            Project_Name="Command Test Project",
            Format="Prepared Speech",
            Duration_Min=5,
            Duration_Max=7,
            Purpose="Purpose check"
        )
        db.session.add(proj)
        db.session.flush()

        pp = PathwayProject(
            path_id=2,
            project_id=proj.id,
            code="L2P1",
            level=2,
            type="elective"
        )
        db.session.add(pp)
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        from app.services.command_parser import CommandParser

        # 1. No arguments: list all active pathways
        success, msg = CommandParser.parse_and_execute('/query-pathways', user, env['club_id'])
        assert success
        assert "Dynamic Leadership" in msg
        assert "Presentation Mastery" in msg

        # 2. Pathway level query
        success, msg = CommandParser.parse_and_execute('/query-pathways PM 2', user, env['club_id'])
        assert success
        assert "Presentation Mastery" in msg
        assert "Command Test Project" in msg

        # 3. Project name query
        success, msg = CommandParser.parse_and_execute('/query-pathways --project "Command Test Project"', user, env['club_id'])
        assert success
        assert "Command Test Project" in msg
        assert "Purpose check" in msg
        assert "Presentation Mastery" in msg


def test_ai_manage_excomm_officers(app, setup_ai_environment):
    """Test 'manage_excomm_officers' tool calling by model and correct response execution."""
    env = setup_ai_environment
    with app.app_context():
        # Add MeetingRoles to database for ExComm testing
        pres_role = MeetingRole(name='President', type='officer', needs_approval=False, has_single_owner=True)
        vpe_role = MeetingRole(name='VPE', type='officer', needs_approval=False, has_single_owner=True)
        db.session.add_all([pres_role, vpe_role])
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        
        # Test Case 1: Query ExComm (which doesn't exist initially)
        msg1 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Who are the current excomm officers?",
            mode='ai'
        )
        reply_text, executed_tools = ChatService.process_chat_completion(
            chat_history_list=[msg1],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools) > 0
        query_call = next((t for t in executed_tools if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] in ['query_officers', 'query']), None)
        assert query_call is not None
        assert "no active" in reply_text.lower() or "assign" in reply_text.lower() or "vacant" in reply_text.lower()

        # Test Case 2: Create a new excomm term 26H1
        msg2 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Please create a new ExComm term '26H1' named 'Memory Makers' from 2026-01-01 to 2026-06-30.",
            mode='ai'
        )
        reply_text2, executed_tools2 = ChatService.process_chat_completion(
            chat_history_list=[msg2],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools2) > 0
        create_call = next((t for t in executed_tools2 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'create_term'), None)
        assert create_call is not None
        assert create_call['arguments']['term'] == '26H1'

        # Test Case 3: Set active term to 26H1
        msg3 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Set the active term to 26H1.",
            mode='ai'
        )
        reply_text3, executed_tools3 = ChatService.process_chat_completion(
            chat_history_list=[msg3],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools3) > 0
        active_call = next((t for t in executed_tools3 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'set_active_term'), None)
        assert active_call is not None
        assert active_call['arguments']['term'] == '26H1'

        # Test Case 4: Update ExComm Officer (President) to John Doe under active term 26H1
        msg4 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Update the club President to John Doe.",
            mode='ai'
        )
        reply_text4, executed_tools4 = ChatService.process_chat_completion(
            chat_history_list=[msg4],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools4) > 0
        update_call = next((t for t in executed_tools4 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] in ['update_officer', 'update']), None)
        assert update_call is not None
        assert 'john' in update_call['arguments']['contact_name'].lower()
        
        # Test Case 5: Query officers of term 26H1 (should now show President: John Doe)
        msg5 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me the roster of excomm term 26H1.",
            mode='ai'
        )
        reply_text5, executed_tools5 = ChatService.process_chat_completion(
            chat_history_list=[msg5],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools5) > 0
        query_call2 = next((t for t in executed_tools5 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'query_officers'), None)
        assert query_call2 is not None
        assert query_call2['arguments']['term'] == '26H1'
        assert "President" in reply_text5 and "John Doe" in reply_text5

        # Test Case 6: Create another excomm term 26H2
        msg6 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Please create a new ExComm term '26H2' named 'Next Gen' from 2026-07-01 to 2026-12-31.",
            mode='ai'
        )
        reply_text6, executed_tools6 = ChatService.process_chat_completion(
            chat_history_list=[msg6],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools6) > 0
        create_call2 = next((t for t in executed_tools6 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'create_term'), None)
        assert create_call2 is not None
        assert create_call2['arguments']['term'] == '26H2'
        
        # Test Case 7: Update President of term 26H2 to John Doe
        msg7 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Assign John Doe as President for the excomm term 26H2.",
            mode='ai'
        )
        reply_text7, executed_tools7 = ChatService.process_chat_completion(
            chat_history_list=[msg7],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools7) > 0
        update_call2 = next((t for t in executed_tools7 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'update_officer'), None)
        assert update_call2 is not None
        assert update_call2['arguments']['term'] == '26H2'
        assert 'john' in update_call2['arguments']['contact_name'].lower()
        
        # Test Case 8: Query officers of term 26H2
        msg8 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me the officers of excomm term 26H2.",
            mode='ai'
        )
        reply_text8, executed_tools8 = ChatService.process_chat_completion(
            chat_history_list=[msg8],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools8) > 0
        query_call3 = next((t for t in executed_tools8 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'query_officers'), None)
        assert query_call3 is not None
        assert query_call3['arguments']['term'] == '26H2'
        assert "President" in reply_text8 and "John Doe" in reply_text8
        
        # Test Case 9: List excomm terms
        msg9 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="List all the excomm terms.",
            mode='ai'
        )
        reply_text9, executed_tools9 = ChatService.process_chat_completion(
            chat_history_list=[msg9],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools9) > 0
        terms_call = next((t for t in executed_tools9 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'query_terms'), None)
        assert terms_call is not None
        assert "26H2" in reply_text9 and "26H1" in reply_text9


def test_ai_manage_waitlist(app, setup_ai_environment):
    """Test 'manage_waitlist' tool calling by model and execution."""
    env = setup_ai_environment
    with app.app_context():
        # Seed project and pathway-project mapping so resolving works
        from app.models import Project, PathwayProject
        proj = Project(
            Project_Name="Ice Breaker",
            Format="Prepared Speech",
            Duration_Min=4,
            Duration_Max=6
        )
        db.session.add(proj)
        db.session.flush()
        
        pp1 = PathwayProject(
            path_id=1,  # DL
            project_id=proj.id,
            code="L1P1",
            level=1,
            type="required"
        )
        pp2 = PathwayProject(
            path_id=2,  # PM
            project_id=proj.id,
            code="L1P1",
            level=1,
            type="required"
        )
        db.session.add_all([pp1, pp2])
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        
        # Test Case 1: Join waitlist for Prepared Speaker
        msg1 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Put John Doe on the waitlist for Prepared Speaker in meeting 100.",
            mode='ai'
        )
        reply_text1, executed_tools1 = ChatService.process_chat_completion(
            chat_history_list=[msg1],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools1) > 0
        create_call = next((t for t in executed_tools1 if t['name'] == 'manage_waitlist' and t['arguments']['action'] in ('create', 'join')), None)
        assert create_call is not None
        assert create_call['arguments']['meeting_identifier'] == '100'
        assert 'john' in create_call['arguments']['contact_name'].lower()
        assert 'speaker' in create_call['arguments']['role_name'].lower()

        # Test Case 2: Query waitlist
        msg2 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Query the waitlist for meeting 100.",
            mode='ai'
        )
        reply_text2, executed_tools2 = ChatService.process_chat_completion(
            chat_history_list=[msg2],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools2) > 0
        query_call = next((t for t in executed_tools2 if t['name'] == 'manage_waitlist' and t['arguments']['action'] == 'query'), None)
        assert query_call is not None
        assert "Prepared Speaker" in reply_text2 and "John Doe" in reply_text2

        # Test Case 3: Update waitlist preferences
        msg3 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Update John Doe's waitlist preferences for Prepared Speaker in meeting 100 with pathway 'Presentation Mastery', project 'Ice Breaker', and title 'My Test Speech'.",
            mode='ai'
        )
        reply_text3, executed_tools3 = ChatService.process_chat_completion(
            chat_history_list=[msg3],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools3) > 0
        update_call = next((t for t in executed_tools3 if t['name'] == 'manage_waitlist' and t['arguments']['action'] == 'update'), None)
        assert update_call is not None
        assert 'john' in update_call['arguments']['contact_name'].lower()
        assert 'presentation mastery' in update_call['arguments']['pathway_name'].lower()
        assert 'ice breaker' in update_call['arguments']['project_name'].lower()
        assert 'my test speech' in update_call['arguments']['speech_title'].lower()

        # Test Case 4: Approve/promote waitlist
        msg4 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Approve the waitlist for Prepared Speaker in meeting 100.",
            mode='ai'
        )
        reply_text4, executed_tools4 = ChatService.process_chat_completion(
            chat_history_list=[msg4],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools4) > 0
        approve_call = next((t for t in executed_tools4 if t['name'] == 'manage_waitlist' and t['arguments']['action'] == 'approve'), None)
        assert approve_call is not None
        
        # Test Case 5: Remove from waitlist (leave waitlist)
        from app.services.chat_tool_executor import ChatToolExecutor
        ChatToolExecutor.tool_manage_waitlist(
            {'action': 'create', 'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'},
            user,
            env['club_id']
        )
        db.session.commit()
        
        msg5 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Remove John Doe from the waitlist for Prepared Speaker in meeting 100.",
            mode='ai'
        )
        reply_text5, executed_tools5 = ChatService.process_chat_completion(
            chat_history_list=[msg5],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools5) > 0
        remove_call = next((t for t in executed_tools5 if t['name'] == 'manage_waitlist' and t['arguments']['action'] == 'remove'), None)
        assert remove_call is not None
        assert 'john' in remove_call['arguments']['contact_name'].lower()


def test_command_parser_waitlist(app, setup_ai_environment):
    """Test '/waitlist' CLI command parsing and execution."""
    env = setup_ai_environment
    with app.app_context():
        # Seed project and pathway-project mapping so resolving works
        from app.models import Project, PathwayProject
        proj = Project(
            Project_Name="Ice Breaker",
            Format="Prepared Speech",
            Duration_Min=4,
            Duration_Max=6
        )
        db.session.add(proj)
        db.session.flush()
        
        pp1 = PathwayProject(
            path_id=1,  # DL
            project_id=proj.id,
            code="L1P1",
            level=1,
            type="required"
        )
        pp2 = PathwayProject(
            path_id=2,  # PM
            project_id=proj.id,
            code="L1P1",
            level=1,
            type="required"
        )
        db.session.add_all([pp1, pp2])
        db.session.commit()

        user = db.session.get(User, env['user_id'])
        from app.services.command_parser import CommandParser
        
        # 1. Join waitlist
        success, msg = CommandParser.parse_and_execute('/waitlist join 100 "Prepared Speaker" "John Doe" "Dynamic Leadership" "Ice Breaker" "Command Speech"', user, env['club_id'])
        assert success, f"Join failed: {msg}"
        assert "Successfully added" in msg
        
        # 2. Update waitlist
        success, msg = CommandParser.parse_and_execute('/waitlist update 100 "Prepared Speaker" "John Doe" "Presentation Mastery" "Ice Breaker" "New Title"', user, env['club_id'])
        assert success, f"Update failed: {msg}"
        assert "Successfully updated" in msg
        
        # 3. Query waitlist
        success, msg = CommandParser.parse_and_execute('/waitlist query 100', user, env['club_id'])
        assert success, f"Query failed: {msg}"
        assert "Prepared Speaker" in msg
        assert "John Doe" in msg
        
        # 4. Approve waitlist
        success, msg = CommandParser.parse_and_execute('/waitlist approve 100 "Prepared Speaker"', user, env['club_id'])
        assert success, f"Approve failed: {msg}"
        assert "Successfully approved" in msg
        
        # 5. Remove from waitlist
        CommandParser.parse_and_execute('/waitlist join 100 "Prepared Speaker" "John Doe"', user, env['club_id'])
        success, msg = CommandParser.parse_and_execute('/waitlist remove 100 "Prepared Speaker" "John Doe"', user, env['club_id'])
        assert success, f"Remove failed: {msg}"
        assert "Successfully removed" in msg


# --- manage_meeting_sessions (direct tool tests; no LLM dependency) ---

def _make_prepared_speech_log(meeting, st, seq, title, owner=None, pathway='Dynamic Leadership'):
    """Helper: create a SessionLog row mirroring a real Prepared Speech entry."""
    log = SessionLog(
        meeting_id=meeting.id,
        Meeting_Seq=seq,
        Type_ID=st.id,
        Session_Title=title,
        Duration_Min=5,
        Duration_Max=7,
        pathway=pathway,
        state='active',
    )
    db.session.add(log)
    db.session.flush()
    if owner:
        from app.services.role_service import RoleService
        RoleService.assign_meeting_role(log, [owner.id], is_admin=True)
        db.session.flush()
    return log


def test_manage_sessions_add_prepared_speech(app, setup_ai_environment):
    """Adding a new Prepared Speech row lands after the last Prepared Speech and gets a project_code.

    Regression: this test now binds the fixture's SessionType to the real club_id
    so the SessionType.get_id_by_title() helper returns a real ID. The bug was
    that the helper returns an int, and the add() method was using the int as
    a SessionType object (accessing .Duration_Min on it), which worked in tests
    with a club_id-less SessionType (helper returned None → fallback to a real
    object) but crashed at runtime in production.
    """
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        st = SessionType.query.filter_by(Title='Prepared Speech').first()
        # Bind the SessionType to the real club_id to mirror production
        st.club_id = env['club_id']
        meeting = db.session.get(Meeting, env['meeting_id'])
        # Give John a Current_Path so derive_project_code can resolve a project_code
        john = db.session.get(Contact, env['john_id'])
        john.Current_Path = 'Dynamic Leadership'
        db.session.commit()

        result = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'add', 'meeting_identifier': '100',
             'session_type': 'Prepared Speech', 'session_title': 'Speech 2', 'owner_name': 'John Doe'},
            user, env['club_id'],
        )
        assert result['success'], result.get('message')
        new_id = result['session_log_id']
        new_log = db.session.get(SessionLog, new_id)
        assert new_log is not None
        assert new_log.Type_ID == st.id
        assert new_log.Session_Title == 'Speech 2'
        assert new_log.Meeting_Seq == 2  # appended after existing seq=1
        # pathway column is stored (project_code derivation requires a real
        # project+pathway link, which the minimal test fixture doesn't seed)
        assert new_log.pathway == 'Dynamic Leadership'


def test_manage_sessions_add_no_perm(app, setup_ai_environment):
    """is_authorized(Permissions.MEETING_MANAGE) returns False for a permless user.

    The test fixture logs in a user with the Staff role (all permissions), so
    we cannot rely on Flask-Login's current_user. Instead we call is_authorized
    directly with a fresh user that has no roles attached.
    """
    from app.auth.utils import is_authorized
    from app.models import AuthRole
    env = setup_ai_environment
    with app.app_context():
        permless_role = AuthRole.query.filter_by(name='Permless').first()
        if not permless_role:
            permless_role = AuthRole(name='Permless', level=0)
            db.session.add(permless_role)
            db.session.flush()
        no_perm_user = User(username='noperm', email='np@x.com', status='active')
        no_perm_user.set_password('x')
        no_perm_user.roles.append(permless_role)
        db.session.add(no_perm_user)
        db.session.commit()

        # Direct call to is_authorized with a non-current user
        from app.auth.permissions import Permissions
        # Patch flask_login.current_user for the duration of the check
        from unittest.mock import patch
        from app.auth import utils as auth_utils
        with patch.object(auth_utils, 'current_user', no_perm_user):
            assert is_authorized(Permissions.MEETING_MANAGE) is False
            assert is_authorized(Permissions.MEETING_CREATE) is False


def test_manage_sessions_update_title_and_duration(app, setup_ai_environment):
    """Update changes Session_Title and Duration_Max; existing seq preserved."""
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        result = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'update', 'meeting_identifier': '100',
             'session_log_id': env['log_id'],
             'session_title': 'Renamed Speech', 'duration_max': 10},
            user, env['club_id'],
        )
        assert result['success'], result.get('message')
        log = db.session.get(SessionLog, env['log_id'])
        assert log.Session_Title == 'Renamed Speech'
        assert log.Duration_Max == 10


def test_manage_sessions_move_to_front(app, setup_ai_environment):
    """Move the last session to position 1; seqs renumbered 1..N contiguously."""
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        st = SessionType.query.filter_by(Title='Prepared Speech').first()
        meeting = db.session.get(Meeting, env['meeting_id'])
        # Add a 2nd row at the end (seq=2)
        log2 = _make_prepared_speech_log(meeting, st, seq=2, title='Speech 2')
        db.session.commit()
        log2_id = log2.id

        result = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'move', 'meeting_identifier': '100',
             'session_log_id': log2_id, 'insert_position': 1},
            user, env['club_id'],
        )
        assert result['success'], result.get('message')
        moved = db.session.get(SessionLog, log2_id)
        original = db.session.get(SessionLog, env['log_id'])
        assert moved.Meeting_Seq == 1
        assert original.Meeting_Seq == 2
        # Verify contiguous 1..N
        all_seqs = sorted(l.Meeting_Seq for l in meeting.session_logs)
        assert all_seqs == list(range(1, len(all_seqs) + 1))


def test_manage_sessions_delete_with_owner(app, setup_ai_environment):
    """Delete a log that has an owner: owner is released, waitlists cleared, log gone."""
    from app.services.chat_tool_executor import ChatToolExecutor
    from app.models import OwnerMeetingRoles, Waitlist
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        st = SessionType.query.filter_by(Title='Prepared Speech').first()
        meeting = db.session.get(Meeting, env['meeting_id'])
        log2 = _make_prepared_speech_log(meeting, st, seq=2, title='To delete',
                                         owner=db.session.get(Contact, env['john_id']))
        db.session.commit()
        log2_id = log2.id

        # Add a waitlist entry to verify cleanup
        wl = Waitlist(session_log_id=log2_id, contact_id=env['john_id'])
        db.session.add(wl)
        db.session.commit()

        result = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'delete', 'meeting_identifier': '100', 'session_log_id': log2_id},
            user, env['club_id'],
        )
        assert result['success'], result.get('message')

        assert db.session.get(SessionLog, log2_id) is None
        assert OwnerMeetingRoles.query.filter_by(session_log_id=log2_id).count() == 0
        assert Waitlist.query.filter_by(session_log_id=log2_id).count() == 0
        # Remaining log renumbered to seq=1
        assert db.session.get(SessionLog, env['log_id']).Meeting_Seq == 1


def test_manage_sessions_delete_no_perm(app, setup_ai_environment):
    """AGENDA_EDIT alone is not enough for delete; AGENDA_DELETE required.

    Verified via is_authorized rather than the full tool flow (see comment
    on test_manage_sessions_add_no_perm for why we don't logout/login).
    """
    from app.auth.utils import is_authorized
    from app.models import AuthRole, UserClub
    from app.models.permission import Permission
    from app.auth.permissions import Permissions
    from unittest.mock import patch
    from app.auth import utils as auth_utils
    env = setup_ai_environment
    with app.app_context():
        # Create a user that has MEETING_MANAGE but NOT MEETING_CREATE
        editor_role = AuthRole(name='EditorNoDelete', level=1)
        db.session.add(editor_role)
        db.session.flush()
        edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if edit_perm:
            editor_role.permissions.append(edit_perm)
        db.session.flush()
        edit_user = User(username='editonly', email='eo@x.com', status='active')
        edit_user.set_password('x')
        edit_user.roles.append(editor_role)
        db.session.add(edit_user)
        db.session.flush()
        db.session.add(UserClub(user_id=edit_user.id, club_id=env['club_id'],
                                contact_id=env['john_id'], club_role_level=1))
        db.session.commit()

        with patch.object(auth_utils, 'current_user', edit_user):
            assert is_authorized(Permissions.MEETING_MANAGE) is True
            assert is_authorized(Permissions.MEETING_CREATE) is False


def test_manage_sessions_query_returns_companion(app, setup_ai_environment):
    """Query of a Prepared Speech surfaces its companion Evaluation/IE log IDs."""
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        st = SessionType.query.filter_by(Title='Prepared Speech').first()
        eval_st = SessionType.query.filter(func.lower(SessionType.Title) == 'evaluation').first()
        ie_st = SessionType.query.filter(func.lower(SessionType.Title) == 'individual evaluator').first()
        if not (eval_st and ie_st):
            # Seed the missing session types for this test only
            from app.models import MeetingRole
            if not eval_st:
                eval_role = MeetingRole.query.filter_by(name='Evaluator').first()
                eval_st = SessionType(Title='Evaluation', Duration_Min=2, Duration_Max=3, role_id=eval_role.id if eval_role else None)
                db.session.add(eval_st)
            if not ie_st:
                ie_role = MeetingRole.query.filter_by(name='Individual Evaluator').first()
                ie_st = SessionType(Title='Individual Evaluator', Duration_Min=1, Duration_Max=1, role_id=ie_role.id if ie_role else None)
                db.session.add(ie_st)
            db.session.flush()

        meeting = db.session.get(Meeting, env['meeting_id'])
        speaker = db.session.get(Contact, env['john_id'])
        speech = _make_prepared_speech_log(meeting, st, seq=2, title='Ice Breaker', owner=speaker)
        eval_log = _make_prepared_speech_log(meeting, eval_st, seq=3, title='Evaluation for John Doe', owner=speaker)
        ie_log = _make_prepared_speech_log(meeting, ie_st, seq=4, title='Individual Evaluator for John Doe', owner=speaker)
        db.session.commit()

        result = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'query', 'meeting_identifier': '100',
             'session_type': 'Prepared Speech', 'include_companions': True},
            user, env['club_id'],
        )
        assert result['success'], result.get('message')
        target = next(s for s in result['sessions'] if s['id'] == speech.id)
        comps = target['companions']
        assert comps['evaluation_id'] == eval_log.id
        assert comps['evaluator_id'] == ie_log.id


def test_manage_sessions_add_chain_companion_evaluation(app, setup_ai_environment):
    """Two chained add calls (Prepared Speech + Evaluation) succeed back-to-back,
    producing two rows in the right shape. The companion-link lookup itself is
    covered by test_manage_sessions_query_returns_companion (which uses a
    fixture that wires the SessionType.role relationship)."""
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        eval_st = SessionType.query.filter(func.lower(SessionType.Title) == 'evaluation').first()
        if not eval_st:
            eval_st = SessionType(Title='Evaluation', Duration_Min=2, Duration_Max=3)
            db.session.add(eval_st)
            db.session.flush()

        # Chain 1: Prepared Speech
        r1 = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'add', 'meeting_identifier': '100',
             'session_type': 'Prepared Speech', 'session_title': 'Speech 2',
             'owner_name': 'John Doe'},
            user, env['club_id'],
        )
        assert r1['success'], r1.get('message')
        # Chain 2: companion Evaluation (same turn, same owner, name in title)
        r2 = ChatToolExecutor.tool_manage_meeting_sessions(
            {'action': 'add', 'meeting_identifier': '100',
             'session_type': 'Evaluation', 'session_title': 'Evaluation for John Doe',
             'owner_name': 'John Doe'},
            user, env['club_id'],
        )
        assert r2['success'], r2.get('message')

        # Both rows should exist in the meeting
        meeting = db.session.get(Meeting, env['meeting_id'])
        titles = sorted([l.Session_Title for l in meeting.session_logs if l.Session_Title])
        assert 'Speech 2' in titles
        # The Evaluation title was normalized to just the speaker name
        # (the UI auto-prepends 'Evaluator for ', so the stored title must
        # not contain a prefix or the display would double up).
        assert 'John Doe' in titles
        assert 'Evaluation for John Doe' not in titles
        # The new rows sit at the end of the agenda
        assert r1['new_seq'] >= 2
        assert r2['new_seq'] > r1['new_seq']


def test_manage_sessions_evaluation_title_normalization(app, setup_ai_environment):
    """Regression: when the LLM passes a 'for X' / 'of X' prefix on an
    Evaluation row, the tool strips it so the UI's auto-prepend doesn't
    double up. The agenda template renders 'Evaluator for ' + Session_Title
    for Evaluation rows (see app/templates/agenda.html:260-261)."""
    from app.services.chat_tool_executor import ChatToolExecutor
    env = setup_ai_environment
    with app.app_context():
        user = db.session.get(User, env['user_id'])
        eval_st = SessionType.query.filter(func.lower(SessionType.Title) == 'evaluation').first()
        if not eval_st:
            eval_st = SessionType(Title='Evaluation', Duration_Min=2, Duration_Max=3)
            db.session.add(eval_st)
            db.session.flush()

        cases = [
            ('Evaluation for Shark Liu',  'Shark Liu'),
            ('evaluation for Shark Liu',  'Shark Liu'),  # case-insensitive
            ('Evaluator for Kyle Wei',    'Kyle Wei'),   # wrong prefix also caught
            ('EVALUATION FOR Kyle Wei',   'Kyle Wei'),
            ('Evaluation of Shark Liu',   'Shark Liu'),  # "of " variant
            ('Evaluation: Shark Liu',     'Shark Liu'),  # colon variant
            ('Shark Liu',                 'Shark Liu'),  # already-clean input passes through
        ]
        for passed_title, expected_stored in cases:
            r = ChatToolExecutor.tool_manage_meeting_sessions(
                {'action': 'add', 'meeting_identifier': '100',
                 'session_type': 'Evaluation', 'session_title': passed_title,
                 'owner_name': 'John Doe'},
                user, env['club_id'],
            )
            assert r['success'], f"add failed for {passed_title!r}: {r.get('message')}"
            stored = db.session.get(SessionLog, r['session_log_id'])
            assert stored.Session_Title == expected_stored, \
                f"input {passed_title!r} stored as {stored.Session_Title!r}, expected {expected_stored!r}"


def test_update_project_details_tool(app, setup_ai_environment):
    """Test the update_project_details tool directly under various scenarios."""
    from app.services.chat_tool_executor import ChatToolExecutor
    from app.models import Project, PathwayProject, OwnerMeetingRoles, SessionLog, User
    from app.models.roster import Waitlist
    env = setup_ai_environment

    with app.app_context():
        # Setup: seed projects for test cases
        p1 = Project(Project_Name="DL Required Speech", Format="Prepared Speech", Duration_Min=5, Duration_Max=7)
        p2 = Project(Project_Name="PM Elective One", Format="Prepared Speech", Duration_Min=5, Duration_Max=7)
        p3 = Project(Project_Name="PM Elective Two", Format="Prepared Speech", Duration_Min=5, Duration_Max=7)
        db.session.add_all([p1, p2, p3])
        db.session.flush()

        pp1 = PathwayProject(path_id=1, project_id=p1.id, code="4.1", level=4, type="required")
        # Share same code PM3.2
        pp2 = PathwayProject(path_id=2, project_id=p2.id, code="3.2", level=3, type="elective")
        pp3 = PathwayProject(path_id=2, project_id=p3.id, code="3.2", level=3, type="elective")
        db.session.add_all([pp1, pp2, pp3])
        db.session.flush()

        # Assign John Doe to SessionLog log_id on Meeting 100
        log = db.session.get(SessionLog, env['log_id'])
        mr = log.session_type.role
        omr = OwnerMeetingRoles(
            meeting_id=env['meeting_id'],
            role_id=mr.id,
            contact_id=env['john_id'],
            session_log_id=log.id
        )
        db.session.add(omr)
        db.session.commit()

        user = db.session.get(User, env['user_id'])

        # Case 1: Successful update with unique project code
        res1 = ChatToolExecutor.tool_update_project_details(
            {
                'meeting_identifier': '100',
                'contact_name': 'John Doe',
                'project_code': 'DL4.1',
                'speech_title': 'Success Speech'
            },
            user, env['club_id']
        )
        assert res1['success'], res1.get('message')
        assert "Successfully updated" in res1['message']
        
        # Verify db updates
        db.session.refresh(log)
        assert log.Session_Title == 'Success Speech'
        assert log.Project_ID == p1.id
        assert log.project_code == 'DL4.1'
        assert log.pathway == 'Dynamic Leadership'

        # Case 2: Duplicate project codes (Electives) with no project_name should return failure with options
        res2 = ChatToolExecutor.tool_update_project_details(
            {
                'meeting_identifier': '100',
                'contact_name': 'John Doe',
                'project_code': 'PM3.2',
                'speech_title': 'Ambiguous Speech'
            },
            user, env['club_id']
        )
        assert not res2['success']
        assert "Multiple projects" in res2['message']
        assert "PM Elective One" in res2['message']
        assert "PM Elective Two" in res2['message']

        # Case 3: Duplicate project codes resolved by providing project_name
        res3 = ChatToolExecutor.tool_update_project_details(
            {
                'meeting_identifier': '100',
                'contact_name': 'John Doe',
                'project_code': 'PM3.2',
                'project_name': 'PM Elective Two',
                'speech_title': 'Resolved Speech'
            },
            user, env['club_id']
        )
        assert res3['success'], res3.get('message')
        db.session.refresh(log)
        assert log.Session_Title == 'Resolved Speech'
        assert log.Project_ID == p3.id

        # Case 4: Meeting not found
        res4 = ChatToolExecutor.tool_update_project_details(
            {
                'meeting_identifier': '9999',
                'contact_name': 'John Doe',
                'project_code': 'DL4.1'
            },
            user, env['club_id']
        )
        assert not res4['success']
        assert "not found" in res4['message']




