import pytest
from unittest.mock import patch
from app.models import db, Contact, Pathway, Project, SessionLog, SessionType, Meeting, MeetingRole, PathwayProject

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
        log.owners.append(contact)
        db.session.add(log)
        db.session.commit()
        
        log_id = log.id
        project_id = proj.id
        meeting_id = meeting.id

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
                'owner_ids': [contact.id]
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
        log.owners.append(guest_contact)
        db.session.add(log)
        db.session.commit()
        
        log_id = log.id

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
                'owner_ids': [guest_contact.id]
            }
        )
        assert resp_update.status_code == 200
        data_update = resp_update.get_json()
        assert data_update.get('success') is True
        assert data_update.get('pathway') == 'Non Pathway'
        
        with app.app_context():
            updated_log = SessionLog.query.get(log_id)
            assert updated_log.pathway == "Non Pathway"


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
                        'type_id': st.id,
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
                role_id=role.id,
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


