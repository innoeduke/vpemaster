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
        for attr in dir(Permissions):
            if attr.isupper() and not attr.startswith('_'):
                name = getattr(Permissions, attr)
                if attr in ['SYSADMIN', 'CLUBADMIN', 'STAFF', 'USER']:
                    continue
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
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'assign_role'
        assert tool_call['arguments']['meeting_identifier'] == '100'
        assert 'john' in tool_call['arguments']['contact_name'].lower()
        assert 'speaker' in tool_call['arguments']['role_name'].lower()


def test_ai_cancel_role(app, setup_ai_environment):
    """Test 'cancel_role' tool calling by model."""
    env = setup_ai_environment
    with app.app_context():
        # First assign John Doe to role so cancel makes sense
        from app.services.chat_tool_executor import ChatToolExecutor
        ChatToolExecutor.tool_assign_role(
            {'meeting_identifier': '100', 'role_name': 'Prepared Speaker', 'contact_name': 'John Doe'},
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
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'cancel_role'
        assert tool_call['arguments']['meeting_identifier'] == '100'
        assert 'john' in tool_call['arguments']['contact_name'].lower()
        assert 'speaker' in tool_call['arguments']['role_name'].lower()


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
        assert tool_call['name'] == 'get_role_assignments'
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
        assert tool_call['name'] == 'get_available_roles'
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
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_voting_results'
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
        tool_call = executed_tools[0]
        assert tool_call['name'] == 'get_meeting_agenda'
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
        
        try:
            assert len(executed_tools) > 0
            tool_call = next((t for t in executed_tools if t['name'] == 'update_meeting_status' and t['arguments']['status'] == 'finished'), None)
            assert tool_call is not None
            assert tool_call['arguments']['meeting_identifier'] in ['100', '#100']
            # The reply text should contain educational info explaining linear progression or starting the meeting
            assert any(word in reply_text.lower() for word in ["not started", "linear", "start", "progression", "running"])
        except AssertionError as e:
            print(f"\n[DEBUG] test_ai_finish_unstarted_meeting_fails: executed_tools={executed_tools}, reply_text={reply_text}")
            raise e


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

        # Test Case 2: Update ExComm Officer (President) to John Doe (active term will be created automatically)
        msg2 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Update the club President to John Doe.",
            mode='ai'
        )
        reply_text2, executed_tools2 = ChatService.process_chat_completion(
            chat_history_list=[msg2],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools2) > 0
        update_call = next((t for t in executed_tools2 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] in ['update_officer', 'update']), None)
        assert update_call is not None
        assert 'john' in update_call['arguments']['contact_name'].lower()
        
        # Test Case 3: Create a new excomm term 26H2
        msg3 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Please create a new ExComm term '26H2' named 'Next Gen' from 2026-07-01 to 2026-12-31.",
            mode='ai'
        )
        reply_text3, executed_tools3 = ChatService.process_chat_completion(
            chat_history_list=[msg3],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools3) > 0
        create_call = next((t for t in executed_tools3 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'create_term'), None)
        assert create_call is not None
        assert create_call['arguments']['term'] == '26H2'
        
        # Test Case 4: Update President of term 26H2 to John Doe
        msg4 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Assign John Doe as President for the excomm term 26H2.",
            mode='ai'
        )
        reply_text4, executed_tools4 = ChatService.process_chat_completion(
            chat_history_list=[msg4],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools4) > 0
        update_call2 = next((t for t in executed_tools4 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'update_officer'), None)
        assert update_call2 is not None
        assert update_call2['arguments']['term'] == '26H2'
        assert 'john' in update_call2['arguments']['contact_name'].lower()
        
        # Test Case 5: Query officers of term 26H2
        msg5 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Show me the officers of excomm term 26H2.",
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
        assert query_call2['arguments']['term'] == '26H2'
        assert "President" in reply_text5 and "John Doe" in reply_text5
        
        # Test Case 6: List excomm terms
        msg6 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="List all the excomm terms.",
            mode='ai'
        )
        reply_text6, executed_tools6 = ChatService.process_chat_completion(
            chat_history_list=[msg6],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools6) > 0
        terms_call = next((t for t in executed_tools6 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'query_terms'), None)
        assert terms_call is not None
        assert "26H2" in reply_text6
        
        # Test Case 7: Set active term to 26H2
        msg7 = ChatMessage(
            user_id=env['user_id'],
            club_id=env['club_id'],
            role='user',
            content="Set the active term to 26H2.",
            mode='ai'
        )
        reply_text7, executed_tools7 = ChatService.process_chat_completion(
            chat_history_list=[msg7],
            user=user,
            club_id=env['club_id'],
            locale='en'
        )
        assert len(executed_tools7) > 0
        active_call = next((t for t in executed_tools7 if t['name'] == 'manage_excomm_officers' and t['arguments']['action'] == 'set_active_term'), None)
        assert active_call is not None
        assert active_call['arguments']['term'] == '26H2'
        assert "active" in reply_text7.lower()



