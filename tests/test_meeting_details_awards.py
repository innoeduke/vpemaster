import pytest
from unittest.mock import patch
from app.models import db, Contact, Meeting, ContactClub, MeetingRole, SessionType, SessionLog, Roster, Ticket

def test_meeting_details_awards_saving(client, app, default_club, staff_user):
    """Verify that updating meeting details with award winners persists the IDs correctly."""
    with app.app_context():
        # Ensure staff role has AGENDA_EDIT permission
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        agenda_edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_edit_perm)
            db.session.commit()

        # Create contacts for the awards
        c_speaker = Contact(Name="Best Speaker Nominee", Type="Member")
        c_evaluator = Contact(Name="Best Evaluator Nominee", Type="Member")
        c_table_topic = Contact(Name="Best Table Topic Nominee", Type="Member")
        c_role_taker = Contact(Name="Best Role Taker Nominee", Type="Member")
        c_debater = Contact(Name="Best Debater Nominee", Type="Member")
        c_lucky = Contact(Name="Lucky Draw Nominee", Type="Member")

        db.session.add_all([c_speaker, c_evaluator, c_table_topic, c_role_taker,
                            c_debater, c_lucky])
        db.session.commit()

        # Associate them with the default club
        for c in [c_speaker, c_evaluator, c_table_topic, c_role_taker,
                  c_debater, c_lucky]:
            cc = ContactClub(contact_id=c.id, club_id=default_club.id)
            db.session.add(cc)

        from datetime import date
        meeting = Meeting(
            Meeting_Number=999,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
            type='Debate',
        )
        db.session.add(meeting)
        db.session.commit()

        meeting_id = meeting.id
        speaker_id = c_speaker.id
        evaluator_id = c_evaluator.id
        table_topic_id = c_table_topic.id
        role_taker_id = c_role_taker.id
        debater_id = c_debater.id
        lucky_id = c_lucky.id

    # Authenticate client
    client.post('/login', data=dict(
        username='staff',
        password='password'
    ))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Call agenda/update route to save awards
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'meeting_title': 'Award Testing Theme',
                'best_speaker_id': str(speaker_id),
                'best_evaluator_id': str(evaluator_id),
                'best_table_topic_id': str(table_topic_id),
                'best_role_taker_id': str(role_taker_id),
                'best_debater_id': str(debater_id),
                'lucky_draw_winner_id': str(lucky_id),
            }
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        with app.app_context():
            updated_meeting = db.session.get(Meeting, meeting_id)
            assert updated_meeting.best_speaker_id == speaker_id
            assert updated_meeting.best_evaluator_id == evaluator_id
            assert updated_meeting.best_table_topic_id == table_topic_id
            assert updated_meeting.best_role_taker_id == role_taker_id
            assert updated_meeting.best_debater_id == debater_id
            assert updated_meeting.lucky_draw_winner_id == lucky_id

        # Now update to None/empty string and check that they are cleared
        resp_clear = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'best_speaker_id': "",
                'best_evaluator_id': "",
                'best_table_topic_id': "",
                'best_role_taker_id': "",
                'best_debater_id': "",
                'lucky_draw_winner_id': "",
            }
        )
        assert resp_clear.status_code == 200
        data_clear = resp_clear.get_json()
        assert data_clear.get('success') is True

        with app.app_context():
            cleared_meeting = db.session.get(Meeting, meeting_id)
            assert cleared_meeting.best_speaker_id is None
            assert cleared_meeting.best_evaluator_id is None
            assert cleared_meeting.best_table_topic_id is None
            assert cleared_meeting.best_role_taker_id is None
            assert cleared_meeting.best_debater_id is None
            assert cleared_meeting.lucky_draw_winner_id is None


def test_best_debater_rejected_on_non_debate_meeting(client, app, default_club, staff_user):
    """Setting best_debater_id on a non-Debate meeting must 400, not silently save."""
    with app.app_context():
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and perm and perm not in staff_role.permissions:
            staff_role.permissions.append(perm)
            db.session.commit()

        c_debater = Contact(Name="Debater Not Allowed", Type="Member")
        db.session.add(c_debater)
        db.session.commit()
        db.session.add(ContactClub(contact_id=c_debater.id, club_id=default_club.id))
        db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=1000,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
            type='Keynote Speech',  # NOT Debate
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id
        debater_id = c_debater.id

    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'best_debater_id': str(debater_id),
            },
        )

    assert resp.status_code == 400
    assert resp.get_json().get('success') is False

    with app.app_context():
        untouched = db.session.get(Meeting, meeting_id)
        assert untouched.best_debater_id is None


def test_lucky_draw_dropdown_excludes_cancelled(client, app, default_club, staff_user):
    """Lucky Draw dropdown should list rostered contacts but skip cancelled-ticket rows."""
    with app.app_context():
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and perm and perm not in staff_role.permissions:
            staff_role.permissions.append(perm)
            db.session.commit()

        # Build the two tickets used by the lucky-draw roster query.
        active_ticket = Ticket.query.filter_by(name='Member').first()
        if not active_ticket:
            active_ticket = Ticket(name='Member')
            db.session.add(active_ticket)
        cancelled_ticket = Ticket.query.filter_by(name='Cancelled').first()
        if not cancelled_ticket:
            cancelled_ticket = Ticket(name='Cancelled')
            db.session.add(cancelled_ticket)
        db.session.commit()

        c_active = Contact(Name="Lucky Active Member", Type="Member")
        c_cancelled = Contact(Name="Lucky Cancelled Member", Type="Member")
        db.session.add_all([c_active, c_cancelled])
        db.session.commit()
        for c in [c_active, c_cancelled]:
            db.session.add(ContactClub(contact_id=c.id, club_id=default_club.id))
        db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=1001,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()

        db.session.add(Roster(meeting_id=meeting.id, contact_id=c_active.id,
                              ticket_id=active_ticket.id, order_number=1))
        db.session.add(Roster(meeting_id=meeting.id, contact_id=c_cancelled.id,
                              ticket_id=cancelled_ticket.id, order_number=2))
        db.session.commit()
        meeting_id = meeting.id
        active_id = c_active.id

    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.get(f'/agenda?meeting_id={meeting_id}')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Lucky Active Member' in html
    assert f'value="{active_id}"' in html
    assert 'Lucky Cancelled Member' not in html


def test_lucky_draw_placeholder_in_modal_for_finished_meeting(client, app, default_club, staff_user):
    """The new select should render in the modal even when the meeting has no roster
    entries yet — the placeholder option should be present."""
    with app.app_context():
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and perm and perm not in staff_role.permissions:
            staff_role.permissions.append(perm)
            db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=1002,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id

    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.get(f'/agenda?meeting_id={meeting_id}')

    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="edit-lucky-draw-winner"' in html
    assert 'id="edit-best-debater"' in html



def test_meeting_details_awards_dropdown_options(client, app, default_club, staff_user):
    """Verify that the dropdown options of the award selects contain only qualified nominees."""
    with app.app_context():
        # Helpers to avoid duplicate role / session type violations
        def get_or_create_role(name, category):
            role = MeetingRole.query.filter_by(name=name, club_id=default_club.id).first()
            if not role:
                role = MeetingRole.query.filter_by(name=name, club_id=None).first()
            if not role:
                role = MeetingRole(name=name, type="standard", needs_approval=False, has_single_owner=True, award_category=category, club_id=default_club.id)
                db.session.add(role)
                db.session.commit()
            else:
                role.award_category = category
                db.session.commit()
            return role

        def get_or_create_st(title, role_id):
            st = SessionType.query.filter_by(Title=title, club_id=default_club.id).first()
            if not st:
                st = SessionType(Title=title, role_id=role_id, club_id=default_club.id)
                db.session.add(st)
                db.session.commit()
            else:
                st.role_id = role_id
                db.session.commit()
            return st

        role_speaker = get_or_create_role("Prepared Speaker", "speaker")
        role_evaluator = get_or_create_role("Evaluator", "evaluator")
        role_tt = get_or_create_role("Table Topics", "table-topic")
        role_rt = get_or_create_role("Ah-Counter", "role-taker")
        
        st_speaker = get_or_create_st("Prepared Speech", role_speaker.id)
        st_evaluator = get_or_create_st("Evaluation", role_evaluator.id)
        st_tt = get_or_create_st("Table Topics", role_tt.id)
        st_rt = get_or_create_st("Ah-Counter", role_rt.id)
        
        # Create contacts
        c_speaker = Contact(Name="Speaker Candidate", Type="Member")
        c_evaluator = Contact(Name="Evaluator Candidate", Type="Member")
        c_table_topic = Contact(Name="Table Topic Candidate", Type="Member")
        c_role_taker = Contact(Name="Role Taker Candidate", Type="Member")
        
        db.session.add_all([c_speaker, c_evaluator, c_table_topic, c_role_taker])
        db.session.commit()
        
        # Associate them with the default club
        for c in [c_speaker, c_evaluator, c_table_topic, c_role_taker]:
            cc = ContactClub(contact_id=c.id, club_id=default_club.id)
            db.session.add(cc)
            
        from datetime import date
        meeting = Meeting(
            Meeting_Number=998,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished'
        )
        db.session.add(meeting)
        db.session.commit()
        
        # Create session logs mapping candidate to each session
        log_sp = SessionLog(meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st_speaker.id, Status="Booked")
        log_ev = SessionLog(meeting_id=meeting.id, Meeting_Seq=2, Type_ID=st_evaluator.id, Status="Booked")
        log_tt = SessionLog(meeting_id=meeting.id, Meeting_Seq=3, Type_ID=st_tt.id, Status="Booked")
        log_rt = SessionLog(meeting_id=meeting.id, Meeting_Seq=4, Type_ID=st_rt.id, Status="Booked")
        
        db.session.add_all([log_sp, log_ev, log_tt, log_rt])
        db.session.flush()
        
        log_sp.owners = [c_speaker]
        log_ev.owners = [c_evaluator]
        log_tt.owners = [c_table_topic]
        log_rt.owners = [c_role_taker]
        db.session.commit()
        
        meeting_id = meeting.id
        speaker_id = c_speaker.id
        evaluator_id = c_evaluator.id
        table_topic_id = c_table_topic.id
        role_taker_id = c_role_taker.id

    # Authenticate client
    client.post('/login', data=dict(
        username='staff',
        password='password'
    ))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Request the agenda page to view the details modal rendering
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.get(f'/agenda?meeting_id={meeting_id}')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        
        # Verify that only the qualified candidates exist in options
        # Speaker dropdown has Speaker Candidate
        assert 'Speaker Candidate' in html
        assert f'value="{speaker_id}"' in html
        
        # Evaluator Candidate
        assert 'Evaluator Candidate' in html
        assert f'value="{evaluator_id}"' in html
        
        # Table Topic Candidate
        assert 'Table Topic Candidate' in html
        assert f'value="{table_topic_id}"' in html
        
        # Role Taker Candidate
        assert 'Role Taker Candidate' in html
        assert f'value="{role_taker_id}"' in html
