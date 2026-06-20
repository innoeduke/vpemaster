import pytest
from datetime import date
from unittest.mock import patch
from app.models import db, Contact, Pathway, Project, SessionLog, SessionType, Meeting, MeetingRole, PathwayProject, OwnerMeetingRoles

def test_presentation_projects_endpoint(client, app, default_club, staff_user):
    """Verify `/speech_log/presentation_projects` endpoint recommended projects and completed filters."""
    with app.app_context():
        # Create presentation series pathways
        sc = Pathway(name="Successful Club Series", abbr="SC", type="presentation", status="active")
        bs = Pathway(name="Better Speaker Series", abbr="BS", type="presentation", status="active")
        db.session.add_all([sc, bs])
        db.session.commit()

        # Create projects
        p1 = Project(Project_Name="Project One", Format="Presentation")
        p2 = Project(Project_Name="Project Two", Format="Presentation")
        p3 = Project(Project_Name="Project Three", Format="Presentation")
        db.session.add_all([p1, p2, p3])
        db.session.commit()

        # Map projects to pathways
        # Level 3: Project One (SC)
        # Level 4: Project Two (SC), Project Three (BS)
        pp1 = PathwayProject(path_id=sc.id, project_id=p1.id, code="294", level=3, type="required")
        pp2 = PathwayProject(path_id=sc.id, project_id=p2.id, code="291", level=4, type="required")
        pp3 = PathwayProject(path_id=bs.id, project_id=p3.id, code="270", level=4, type="required")
        db.session.add_all([pp1, pp2, pp3])
        db.session.commit()

        # Create contact with a standard pathway current path
        standard_path = Pathway(name="Presentation Mastery", abbr="PM", type="pathway", status="active")
        db.session.add(standard_path)
        db.session.commit()

        contact = Contact(Name="Presentation Owner", Type="Member", Current_Path="Presentation Mastery")
        db.session.add(contact)
        db.session.commit()

        contact_id = contact.id
        project_one_id = p1.id
        project_two_id = p2.id
        project_three_id = p3.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # 0. Fetch without level (should default to level 3 since contact's derived level is < 3)
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['target_level'] == 3
    assert len(data['projects']) == 1
    assert data['projects'][0]['id'] == project_one_id

    # 1. Fetch for level 3
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}&level=3')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] is True
    assert data['target_level'] == 3
    assert len(data['projects']) == 1
    assert data['projects'][0]['id'] == project_one_id
    assert data['projects'][0]['Project_Name'] == "Project One"

    # 2. Fetch for level 4
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}&level=4')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['projects']) == 2
    project_ids = [p['id'] for p in data['projects']]
    assert project_two_id in project_ids
    assert project_three_id in project_ids

    # 3. Mark Project Two completed and fetch again for level 4 (should exclude Project Two)
    with app.app_context():
        # Setup finished meeting where contact completed project two
        role = MeetingRole(name="Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Presentation", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        meeting = Meeting(Meeting_Number=105, Meeting_Date=date.today(), status="finished", club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Project_ID=project_two_id,
            Status="Completed"
        )
        db.session.add(log)
        db.session.flush()
        
        c = db.session.get(Contact, contact_id)
        log.owners = [c]
        
        omr = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role.id,
            contact_id=contact_id,
            session_log_id=log.id
        )
        db.session.add(omr)
        db.session.commit()

    # Fetch level 4 again - should only return Project Three
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}&level=4')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['projects']) == 1
    assert data['projects'][0]['id'] == project_three_id

    # Fetch level 4 again passing Project Two as current_project_id - should include Project Two
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}&level=4&current_project_id={project_two_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['projects']) == 2

    # 4. Fetch level 4 specifying a different pathway - should return both projects (Project Two is not completed for Dynamic Leadership)
    resp = client.get(f'/speech_log/presentation_projects?contact_id={contact_id}&level=4&pathway=Dynamic+Leadership')
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data['projects']) == 2


def test_presentation_omr_save(client, app, default_club, staff_user):
    """Verify that saving a Presentation log sets omr.target_level but clears target_pathway."""
    with app.app_context():
        # Setup data
        p = Pathway(name="Successful Club Series", abbr="SC", type="presentation", status="active")
        db.session.add(p)
        db.session.commit()

        proj = Project(Project_Name="Project One", Format="Presentation")
        db.session.add(proj)
        db.session.commit()

        pp = PathwayProject(path_id=p.id, project_id=proj.id, code="294", level=3, type="required")
        db.session.add(pp)
        db.session.commit()

        contact = Contact(Name="Presentation Owner 2", Type="Member", Current_Path="Presentation Mastery")
        db.session.add(contact)
        db.session.commit()

        role = MeetingRole(name="Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Presentation", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        meeting = Meeting(Meeting_Number=106, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=1,
            Type_ID=st.id,
            Project_ID=proj.id,
            Status="Booked"
        )
        db.session.add(log)
        db.session.flush()
        
        c = db.session.get(Contact, contact_id := contact.id)
        log.owners = [c]

        omr = OwnerMeetingRoles(
            meeting_id=meeting.id,
            role_id=role.id,
            contact_id=contact_id,
            session_log_id=log.id
        )
        db.session.add(omr)
        db.session.commit()

        log_id = log.id
        project_id = proj.id
        meeting_id = meeting.id
        role_id = role.id

    # Authenticate client
    with client.session_transaction() as sess:
        sess['_user_id'] = str(staff_user.id)
        sess['club_id'] = default_club.id
        sess['_fresh'] = True

    # 1. Save log with pathway="Presentation Mastery" and level=3
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.post(
            f'/speech_log/update/{log_id}',
            json={
                'pathway': 'Presentation Mastery',
                'level': 3,
                'project_id': project_id,
                'session_title': 'My Presentation Speech',
                'owner_ids': [contact_id]
            }
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        with app.app_context():
            # Check OMR target levels
            saved_omr = OwnerMeetingRoles.query.filter_by(
                meeting_id=meeting_id,
                role_id=role_id,
                contact_id=contact_id
            ).first()
            assert saved_omr is not None
            assert saved_omr.target_level == '3'
            assert saved_omr.target_pathway == 'Presentation Mastery'

    # 2. Save log with pathway="Non Pathway"
    with patch('app.speech_logs_routes.is_authorized', return_value=True):
        resp = client.post(
            f'/speech_log/update/{log_id}',
            json={
                'pathway': 'Non Pathway',
                'level': 3,
                'project_id': project_id,
                'session_title': 'My Presentation Speech',
                'owner_ids': [contact_id]
            }
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        with app.app_context():
            saved_omr = OwnerMeetingRoles.query.filter_by(
                meeting_id=meeting_id,
                role_id=role_id,
                contact_id=contact_id
            ).first()
            assert saved_omr is not None
            assert saved_omr.target_level is None
            assert saved_omr.target_pathway is None
