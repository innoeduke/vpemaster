import pytest
from unittest.mock import patch
from app.models import db, Contact, Pathway, Project, SessionLog, SessionType, Meeting, MeetingRole, PathwayProject, ContactPath, ContactClub

def test_speech_log_update_pathway_preserves_manual_selection(client, app, default_club, staff_user):
    """Verify that updating a speech log's pathway preserves the manual selection and updates agenda display."""
    with app.app_context():
        # 1. Create Pathways
        p1 = Pathway(name="Dynamic Leadership", abbr="DL", type="pathway", status="active")
        p2 = Pathway(name="Engaging Humor", abbr="EH", type="pathway", status="active")
        db.session.add_all([p1, p2])
        db.session.commit()
        
        # 2. Create a contact with Dynamic Leadership as current path
        contact = Contact(Name="Path Test User", Type="Member", Current_Path="Dynamic Leadership")
        db.session.add(contact)
        db.session.commit()
        
        # 3. Create a project
        proj = Project(Project_Name="Connect with Storytelling", Format="Prepared Speech")
        db.session.add(proj)
        db.session.commit()
        
        # Create PathwayProject mappings
        pp1 = PathwayProject(path_id=p1.id, project_id=proj.id, code="3.2", level=3, type="required")
        pp2 = PathwayProject(path_id=p2.id, project_id=proj.id, code="3.2", level=3, type="required")
        db.session.add_all([pp1, pp2])
        db.session.commit()
        
        # 4. Create Meeting & SessionType
        role = MeetingRole(name="Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()
        
        st = SessionType(Title="Prepared Speech", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()
        
        from datetime import date
        meeting = Meeting(Meeting_Number=101, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()
        
        # 5. Create SessionLog (initial pathway is DL)
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Project_ID=proj.id,
            Status="Booked",
            pathway="Dynamic Leadership"
        )
        db.session.add(log)
        db.session.flush()
        log.owners = [contact]
        db.session.commit()
        
        log_id = log.id
        project_id = proj.id
        meeting_id = meeting.id
        contact_id = contact.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Call the speech_log update route to change pathway to Engaging Humor
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.post(
            f'/speech_log/update/{log_id}',
            json={
                'pathway': 'Engaging Humor',
                'project_id': project_id,
                'session_title': 'My Ice Breaker Speech',
                'owner_ids': [contact_id]
            }
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        # Verify the returned project code is EH3.2, NOT DL3.2
        assert data.get('project_code') == 'EH3.2'
        
        with app.app_context():
            updated_log = SessionLog.query.get(log_id)
            # The pathway should be the user selected one ("Engaging Humor"), NOT owner's current path ("Dynamic Leadership")
            assert updated_log.pathway == "Engaging Humor"
            # Verify the project code in DB is also updated to EH3.2
            assert updated_log.project_code == 'EH3.2'
            # Verify owner's Current_Path was NOT changed (requirement from edit details modal save)
            assert updated_log.owners[0].Current_Path == "Dynamic Leadership"

    # Now verify the agenda endpoint displays the correct project code ('EH3.2' instead of 'DL3.2')
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.get(f'/api/agenda/get_logs/{meeting_id}')
        assert resp.status_code == 200
        agenda_data = resp.get_json()
        assert agenda_data.get('success') is True
        logs = agenda_data.get('logs_data', [])
        assert len(logs) > 0
        matching_log = next(l for l in logs if l['id'] == log_id)
        assert matching_log['project_code_display'] == 'EH3.2'


def test_guest_without_user_defaults_to_non_pathway(client, app, default_club, staff_user):
    """Verify that a guest contact without a user account defaults to Non Pathway."""
    with app.app_context():
        # Ensure Non Pathway exists in DB
        np_path = Pathway.query.filter_by(name="Non Pathway").first()
        if not np_path:
            np_path = Pathway(name="Non Pathway", abbr="TM", type="others", status="active")
            db.session.add(np_path)
            db.session.commit()
            
        # Create a contact of Type = Guest (and no user account)
        guest_contact = Contact(Name="Guest Path Test User", Type="Guest")
        db.session.add(guest_contact)
        db.session.commit()
        
        # Create Meeting & SessionType
        role = MeetingRole(name="Welcome Officer", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()
        
        st = SessionType(Title="Welcome Officer", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()
        
        from datetime import date
        meeting = Meeting(Meeting_Number=102, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()
        
        # Create SessionLog (initial pathway is empty)
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Status="Booked",
            pathway=None
        )
        db.session.add(log)
        db.session.flush()
        log.owners = [guest_contact]
        db.session.commit()
        
        log_id = log.id
        guest_contact_id = guest_contact.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Call get_speech_log_details route and assert default pathway is "Non Pathway"
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get(f'/speech_log/details/{log_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert data.get('log', {}).get('pathway') == 'Non Pathway'

        # Update pathway to "Non Pathway" and save
        resp_update = client.post(
            f'/speech_log/update/{log_id}',
            json={
                'pathway': 'Non Pathway',
                'session_title': 'Welcome Guest Speech',
                'owner_ids': [guest_contact_id]
            }
        )
        assert resp_update.status_code == 200
        data_update = resp_update.get_json()
        assert data_update.get('success') is True
        assert data_update.get('pathway') == 'Non Pathway'
        
        with app.app_context():
            updated_log = SessionLog.query.get(log_id)
            assert updated_log.pathway is None


def test_functional_role_pathway_save(client, app, default_club, staff_user):
    """Verify that updating a functional role's pathway saves to OwnerMeetingRoles and serializes correctly on get_logs."""
    with app.app_context():
        # Ensure staff role has AGENDA_EDIT permission
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        agenda_edit_perm = Permission.query.filter_by(name=Permissions.AGENDA_EDIT).first()
        if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_edit_perm)
            db.session.commit()

        # Ensure Dynamic Leadership Pathway exists
        p1 = Pathway.query.filter_by(name="Dynamic Leadership").first()
        if not p1:
            p1 = Pathway(name="Dynamic Leadership", abbr="DL", type="pathway", status="active")
            db.session.add(p1)
            db.session.commit()

        # Create contact
        contact = Contact(Name="Functional Role User", Type="Member", Current_Path="Dynamic Leadership")
        db.session.add(contact)
        db.session.commit()

        # Create Meeting & SessionType for Ah-Counter
        role = MeetingRole(name="Ah-Counter", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Ah-Counter", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        from datetime import date
        meeting = Meeting(Meeting_Number=103, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        # Create SessionLog for Ah-Counter (initially DL1)
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Status="Booked",
            pathway="Dynamic Leadership"
        )
        db.session.add(log)
        db.session.flush()

        from app.models import OwnerMeetingRoles
        # Add to OwnerMeetingRoles
        omr = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role.id,
            contact_id=contact.id,
            session_log_id=log.id,
            credential="DL1"
        )
        db.session.add(omr)
        db.session.commit()

        log_id = log.id
        meeting_id = meeting.id
        contact_id = contact.id
        st_id = st.id
        role_id = role.id

    # Authenticate client
    client.post('/login', data=dict(
        username='staff',
        password='password'
    ))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Save details via agenda update (simulate saveChanges in agenda page)
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [
                    {
                        'id': log_id,
                        'meeting_number': 103,
                        'meeting_seq': 1,
                        'start_time': '20:00',
                        'type_id': st_id,
                        'session_title': 'Ah-Counter Report',
                        'owner_ids': [contact_id],
                        'owner_id': contact_id,
                        'credentials': 'DL2',  # Changed level from DL1 to DL2
                        'duration_min': 2,
                        'duration_max': 3,
                        'project_id': None,
                        'status': 'Booked'
                    }
                ]
            }
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        # Verify OwnerMeetingRoles updated
        with app.app_context():
            updated_omr = OwnerMeetingRoles.query.filter_by(
                meeting_id=meeting_id,
                role_id=role_id,
                contact_id=contact_id,
                session_log_id=log_id
            ).first()
            assert updated_omr is not None
            assert updated_omr.credential == 'DL2'

        # Fetch logs via API and assert serialized credentials is DL2
        resp_logs = client.get(f'/api/agenda/get_logs/{meeting_id}')
        assert resp_logs.status_code == 200
        logs_data = resp_logs.get_json()
        assert logs_data.get('success') is True
        logs = logs_data.get('logs_data', [])
        assert len(logs) > 0
        matching_log = next(l for l in logs if l['id'] == log_id)
        assert matching_log['Credentials'] == 'DL2'


def test_evaluation_session_details(client, app, default_club, staff_user):
    """Verify that details endpoint correctly serializes Session_Title for Evaluation session logs."""
    with app.app_context():
        # Create Evaluation session type and role
        role = MeetingRole.query.filter_by(name="Evaluator").first()
        if not role:
            role = MeetingRole(name="Evaluator", type="standard", needs_approval=False, has_single_owner=True)
            db.session.add(role)
            db.session.commit()

        st = SessionType.query.filter_by(Title="Evaluation").first()
        if not st:
            st = SessionType(Title="Evaluation", role_id=role.id, club_id=default_club.id)
            db.session.add(st)
            db.session.commit()

        # Create contact
        contact = Contact(Name="Evaluator Member", Type="Member")
        db.session.add(contact)
        db.session.commit()

        # Create meeting
        from datetime import date
        meeting = Meeting(Meeting_Number=104, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        # Create session log with evaluator as owner and a custom session title (speaker name)
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Status="Completed",
            Session_Title="John Zhang"
        )
        db.session.add(log)
        db.session.flush()
        log.owners = [contact]
        db.session.commit()

        log_id = log.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Get speech details
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get(f'/speech_log/details/{log_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert data.get('log', {}).get('Session_Title') == "John Zhang"
        assert data.get('log', {}).get('session_type_title') == "Evaluation"


def test_functional_role_immediate_update(client, app, default_club, staff_user):
    """Verify that updating a functional role's pathway via speech_log/update endpoint saves to OwnerMeetingRoles."""
    with app.app_context():
        # Create pathway
        p1 = Pathway.query.filter_by(name="Persuasive Influence").first()
        if not p1:
            p1 = Pathway(name="Persuasive Influence", abbr="PI", type="pathway", status="active")
            db.session.add(p1)
            db.session.commit()

        # Create contact
        contact = Contact(Name="Immediate Update User", Type="Member", Current_Path="Persuasive Influence")
        db.session.add(contact)
        db.session.commit()

        # Create Meeting & SessionType for Timer
        role = MeetingRole(name="Timer", type="standard", needs_approval=False, has_single_owner=False)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Timer Introduction", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        from datetime import date
        meeting = Meeting(Meeting_Number=105, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        # Create SessionLog
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=2,
            Type_ID=st.id,
            Status="Booked"
        )
        db.session.add(log)
        db.session.flush()

        from app.models import OwnerMeetingRoles
        # Add to OwnerMeetingRoles
        omr = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role.id,
            contact_id=contact.id,
            session_log_id=None
        )
        db.session.add(omr)
        db.session.commit()

        log_id = log.id
        meeting_id = meeting.id
        contact_id = contact.id
        role_id = role.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Immediate update
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp_update = client.post(
            f'/speech_log/update/{log_id}',
            json={
                'owner_targets': {
                    str(contact_id): {
                        'pathway': 'Persuasive Influence',
                        'level': '2'
                    }
                }
            }
        )
        assert resp_update.status_code == 200
        data_update = resp_update.get_json()
        assert data_update.get('success') is True

        # Verify OwnerMeetingRoles updated
        with app.app_context():
            updated_omr = OwnerMeetingRoles.query.filter_by(
                meeting_id=meeting_id,
                role_id=role_id,
                contact_id=contact_id
            ).first()
            assert updated_omr is not None
            assert updated_omr.target_pathway == 'Persuasive Influence'
            assert updated_omr.target_level == '2'



def test_speech_log_details_includes_registered_paths(client, app, default_club, staff_user):
    """Verify that get_speech_log_details endpoint serializes owner_id and registered_paths, and /api/data/all serializes registered_paths."""
    with app.app_context():
        # Create pathways
        p1 = Pathway(name="Innovative Planning", abbr="IP", type="pathway", status="active")
        p2 = Pathway(name="Presentation Mastery", abbr="PM", type="pathway", status="active")
        db.session.add_all([p1, p2])
        db.session.commit()

        # Create contact
        contact = Contact(Name="Path Test Member", Type="Member")
        db.session.add(contact)
        db.session.commit()

        # Associate contact to club
        cc = ContactClub(contact_id=contact.id, club_id=default_club.id)
        db.session.add(cc)
        db.session.commit()

        # Associate pathways to contact
        cp1 = ContactPath(contact_id=contact.id, path_id=p1.id, status="working")
        cp2 = ContactPath(contact_id=contact.id, path_id=p2.id, status="working")
        db.session.add_all([cp1, cp2])
        db.session.commit()

        # Create meeting & SessionType
        role = MeetingRole(name="Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Prepared Speech", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        from datetime import date
        meeting = Meeting(Meeting_Number=106, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        # Create session log
        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Status="Booked"
        )
        db.session.add(log)
        db.session.flush()
        log.owners = [contact]
        db.session.commit()

        log_id = log.id
        contact_id = contact.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Get speech details
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.get(f'/speech_log/details/{log_id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True
        assert data.get('log', {}).get('owner_id') == contact_id
        # Verify registered paths lists Innovative Planning and Presentation Mastery
        registered_paths = data.get('log', {}).get('registered_paths', [])
        assert "Innovative Planning" in registered_paths
        assert "Presentation Mastery" in registered_paths

    # Get agenda modal data
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp_all = client.get('/api/data/all')
        assert resp_all.status_code == 200
        all_data = resp_all.get_json()
        # Find contact in all_data['contacts']
        contacts = all_data.get('contacts', [])
        test_contact_dict = next((c for c in contacts if c['id'] == contact_id), None)
        assert test_contact_dict is not None
        assert "Innovative Planning" in test_contact_dict['registered_paths']
        assert "Presentation Mastery" in test_contact_dict['registered_paths']


def test_non_pathway_filtering_and_level_resolution(client, app, default_club, staff_user):
    """Verify that filtering by Non Pathway correctly retrieves generic roles and classifies them by active level."""
    from datetime import date, timedelta
    from app.models import Achievement, OwnerMeetingRoles

    with app.app_context():
        # 1. Create Pathway
        p = Pathway(name="Dynamic Leadership", abbr="DL", type="pathway", status="active")
        db.session.add(p)
        db.session.commit()

        # 2. Create User and Contact
        from app.models import User
        user = User(username="nonpath", email="nonpath@member.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        contact = Contact(Name="Non Path Member", Type="Member", Email="nonpath@member.com", Current_Path="Dynamic Leadership")
        db.session.add(contact)
        db.session.commit()

        # Associate contact to club
        cc = ContactClub(contact_id=contact.id, club_id=default_club.id)
        db.session.add(cc)
        db.session.commit()

        # 3. Add a level 1 completion achievement at date.today() - 5 days
        completion_date = date.today() - timedelta(days=5)
        ach = Achievement(
            member_id=str(contact.id),
            user_id=contact.user_id,
            path_name="Dynamic Leadership",
            achievement_type="level-completion",
            level=1,
            issue_date=completion_date
        )
        db.session.add(ach)
        db.session.commit()

        # 4. Create Meetings
        mrole = MeetingRole(name="Ah-Counter", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(mrole)
        db.session.commit()

        st = SessionType(Title="Ah-Counter", role_id=mrole.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        # Meeting 1: Before achievement completion date (should be resolved as Level 1)
        m1 = Meeting(Meeting_Number=201, Meeting_Date=completion_date - timedelta(days=2), club_id=default_club.id)
        # Meeting 2: After achievement completion date (should be resolved as Level 2)
        m2 = Meeting(Meeting_Number=202, Meeting_Date=completion_date + timedelta(days=2), club_id=default_club.id)
        db.session.add_all([m1, m2])
        db.session.commit()

        # 5. Create SessionLogs (generic roles with no pathway)
        log1 = SessionLog(meeting_id=m1.id, Meeting_Seq=1, Type_ID=st.id, Status="Completed", pathway=None)
        log2 = SessionLog(meeting_id=m2.id, Meeting_Seq=1, Type_ID=st.id, Status="Completed", pathway=None)
        db.session.add_all([log1, log2])
        db.session.flush()

        log1.owners = [contact]
        log2.owners = [contact]
        db.session.commit()

        # Add to OwnerMeetingRoles (with target_pathway = None / NULL)
        omr1 = OwnerMeetingRoles(
            meeting_id=m1.id,
            role_id=mrole.id,
            contact_id=contact.id,
            session_log_id=log1.id,
            target_pathway=None,
            target_level=None
        )
        omr2 = OwnerMeetingRoles(
            meeting_id=m2.id,
            role_id=mrole.id,
            contact_id=contact.id,
            session_log_id=log2.id,
            target_pathway=None,
            target_level=None
        )
        db.session.add_all([omr1, omr2])
        db.session.commit()

        contact_id = contact.id
        log1_id = log1.id
        log2_id = log2.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # Call _get_pathway_date_range and assert it returns min/max dates for 'Non Pathway'
    from app.speech_logs_routes import _get_pathway_date_range, _process_logs, _fetch_logs_with_filters
    
    with app.app_context():
        c_obj = db.session.get(Contact, contact_id)
        start_d, end_d = _get_pathway_date_range(c_obj, 'Non Pathway')
        assert start_d == date.min
        assert end_d == date.max

        # Verify get_display_level_and_type directly
        log1_obj = db.session.get(SessionLog, log1_id)
        log2_obj = db.session.get(SessionLog, log2_id)
        
        # Test display level derivation
        lvl1, _, _ = log1_obj.get_display_level_and_type(context_contact=c_obj, context_pathway_name="Non Pathway")
        lvl2, _, _ = log2_obj.get_display_level_and_type(context_contact=c_obj, context_pathway_name="Non Pathway")
        
        assert lvl1 == "1"
        assert lvl2 == "2"

        # Verify filters and log processing
        filters = {
            'meeting_id': None,
            'pathway': 'Non Pathway',
            'level': None,
            'speaker_id': contact_id,
            'status': None,
            'role': None
        }
        with patch('app.speech_logs_routes.current_user', staff_user):
            all_logs = _fetch_logs_with_filters(filters)
            assert len(all_logs) >= 2
            
            # Verify both logs have targets pre-fetched or correctly processed
            from app.speech_logs_routes import _attach_owners
            _attach_owners(all_logs)
            
            grouped_logs = _process_logs(all_logs, filters, pathway_cache={})
        
            # Should be grouped under "1" and "2"
            assert "1" in grouped_logs
            assert "2" in grouped_logs
            
            # Verify the specific log objects are present
            g1_ids = [l.id for l in grouped_logs["1"] if hasattr(l, "id")]
            g2_ids = [l.id for l in grouped_logs["2"] if hasattr(l, "id")]
            
            assert log1_id in g1_ids
            assert log2_id in g2_ids

