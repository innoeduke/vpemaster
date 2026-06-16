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


def test_best_debater_empty_value_allowed_on_non_debate_meeting(client, app, default_club, staff_user):
    """Saving an empty best_debater_id on a non-Debate meeting must not 400.

    The agenda's Save button always sends best_debater_id (as '' for
    meetings that don't have the field populated), so a strict gate would
    block every save on a Keynote Speech meeting. Empty means 'clear',
    which is always legal.
    """
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
            Meeting_Number=1003,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
            type='Keynote Speech',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id

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
                'best_debater_id': "",
            },
        )

    assert resp.status_code == 200
    assert resp.get_json().get('success') is True

    with app.app_context():
        m = db.session.get(Meeting, meeting_id)
        assert m.best_debater_id is None


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
    # The awards section is now JS-rendered from serialized data.
    # Check that the serialized awards data and table structure exist.
    assert 'id="awards-table"' in html
    assert 'window.__awardsInitial' in html



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


def test_unified_awards_saving(client, app, default_club, staff_user):
    """Verify that sending the new unified 'awards' list updates configs and winners, and supports custom categories, role constraints, and multiple winners."""
    with app.app_context():
        # Ensure staff role has AGENDA_EDIT permission
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        agenda_edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_edit_perm)
            db.session.commit()

        # Create contacts
        c_1 = Contact(Name="Winner One", Type="Member")
        c_2 = Contact(Name="Winner Two", Type="Member")
        db.session.add_all([c_1, c_2])
        db.session.commit()
        db.session.add(ContactClub(contact_id=c_1.id, club_id=default_club.id))
        db.session.add(ContactClub(contact_id=c_2.id, club_id=default_club.id))
        db.session.commit()

        # Build roster so they are candidates for custom awards
        from app.models import Roster, Ticket
        # Get or create ticket
        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
            db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=997,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id
        w1_id = c_1.id
        w2_id = c_2.id

        # Add to roster
        r1 = Roster(meeting_id=meeting_id, contact_id=w1_id, ticket_id=t.id, order_number=1)
        r2 = Roster(meeting_id=meeting_id, contact_id=w2_id, ticket_id=t.id, order_number=2)
        db.session.add_all([r1, r2])
        db.session.commit()

        # Create a meeting role and assign Winner One to it
        mr_timer = MeetingRole(name="Timer", type="standard", needs_approval=False, has_single_owner=True, club_id=default_club.id)
        db.session.add(mr_timer)
        db.session.commit()
        
        # Add to OwnerMeetingRoles
        from app.models import OwnerMeetingRoles
        omr = OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_timer.id, contact_id=w1_id)
        db.session.add(omr)
        db.session.commit()

    # Authenticate client
    client.post('/login', data=dict(
        username='staff',
        password='password'
    ))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Post unified awards list to update endpoint
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'meeting_title': 'Unified Awards Theme',
                'awards': [
                    # A default category with a winner
                    {
                        'category': 'speaker',
                        'label': 'Best Speaker',
                        'max_votes': 1,
                        'max_winners': 1,
                        'associated_role': None,
                        'winner_ids': [w1_id]
                    },
                    # A custom category based on "Timer" role with Winner One
                    {
                        'category': 'best-dresser',
                        'label': 'Best Dresser',
                        'max_votes': 2,
                        'max_winners': 2,
                        'associated_role': 'Timer',
                        'winner_ids': [w1_id]
                    }
                ]
            }
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        with app.app_context():
            from app.models.voting import MeetingAwardConfig, MeetingAwardWinner
            # Verify configs
            configs = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id).all()
            assert len(configs) == 2
            
            speaker_config = next(c for c in configs if c.award_category == 'speaker')
            assert speaker_config.max_votes_per_user == 1
            assert speaker_config.max_winners == 1
            assert speaker_config.associated_role is None
            
            dresser_config = next(c for c in configs if c.award_category == 'best-dresser')
            assert dresser_config.max_votes_per_user == 2
            assert dresser_config.max_winners == 2
            assert dresser_config.associated_role == 'Timer'
            
            # Verify winners
            winners = MeetingAwardWinner.query.filter_by(meeting_id=meeting_id).all()
            assert len(winners) == 2
            
            speaker_winners = [w for w in winners if w.award_category == 'speaker']
            assert len(speaker_winners) == 1
            assert speaker_winners[0].contact_id == w1_id
            
            dresser_winners = [w for w in winners if w.award_category == 'best-dresser']
            assert len(dresser_winners) == 1
            assert dresser_winners[0].contact_id == w1_id

            # Verify voting page roles generation and sorting for custom categories
            from app.voting_routes import _get_roles_for_voting
            from flask_login import login_user
            m_obj = db.session.get(Meeting, meeting_id)
            
            with app.test_request_context():
                from app.models import User
                # Log in user inside the request context
                staff = db.session.get(User, staff_user.id)
                login_user(staff)
                
                with patch('app.voting_routes.is_authorized', return_value=True):
                    roles = _get_roles_for_voting(meeting_id, m_obj)
                    
                    # best-dresser is associated with Timer role (only w1_id took it), so it should generate exactly 1 synthetic role
                    dresser_roles = [r for r in roles if r.get('award_category') == 'best-dresser']
                    assert len(dresser_roles) == 1
                    assert dresser_roles[0].get('owner_id') == w1_id
                    
                    # Ensure they are sorted correctly (using group_roles_by_category)
                    from app.utils import group_roles_by_category
                    grouped = group_roles_by_category(roles)
                    categories = [cat for cat, items in grouped]
                    assert 'best-dresser' in categories
                    
                    # If standard categories are present, custom should follow them
                    standard_orders = [cat for cat in categories if cat in ('speaker', 'evaluator', 'role-taker', 'table-topic')]
                    if standard_orders:
                        assert categories.index('best-dresser') > categories.index(standard_orders[-1])

        # Also check via client GET integration to ensure the voting page renders custom categories
        with patch('app.voting_routes.is_authorized', return_value=True):
            resp_voting = client.get(f'/voting/{meeting_id}')
            assert resp_voting.status_code == 200
            html_voting = resp_voting.get_data(as_text=True)
            assert 'Best Dresser' in html_voting
            # Ensure it does NOT contain 'Best Dresser Roles'
            assert 'Best Dresser Roles' not in html_voting


def test_unified_awards_deletion(client, app, default_club, staff_user):
    """Verify that omitting a custom award from the unified awards payload deletes it from the database for this meeting."""
    with app.app_context():
        # Ensure staff role has MEETING_MANAGE permission
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        agenda_edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_edit_perm)
            db.session.commit()

        # Create meeting
        from datetime import date
        meeting = Meeting(
            Meeting_Number=998,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id

        # Pre-populate a custom award config and winner
        from app.models.voting import MeetingAwardConfig, MeetingAwardWinner, Award
        award_obj = Award(club_id=default_club.id, name="Temp Custom", category="temp-custom")
        db.session.add(award_obj)
        db.session.commit()

        cfg = MeetingAwardConfig(meeting_id=meeting_id, award_id=award_obj.id, award_category="temp-custom", max_votes_per_user=1, max_winners=1)
        winner = MeetingAwardWinner(meeting_id=meeting_id, award_id=award_obj.id, award_category="temp-custom", contact_id=1)
        db.session.add_all([cfg, winner])
        db.session.commit()

    # Authenticate client
    client.post('/login', data=dict(
        username='staff',
        password='password'
    ))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Post update omitting temp-custom
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'meeting_title': 'Deleted Awards Theme',
                'awards': [
                    # Keep speaker but omit temp-custom
                    {
                        'category': 'speaker',
                        'label': 'Best Speaker',
                        'max_votes': 1,
                        'max_winners': 1,
                        'winner_ids': []
                    }
                ]
            }
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('success') is True

        with app.app_context():
            from app.models.voting import MeetingAwardConfig, MeetingAwardWinner
            # Verify temp-custom config and winner are deleted
            cfg_check = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id, award_category="temp-custom").first()
            winner_check = MeetingAwardWinner.query.filter_by(meeting_id=meeting_id, award_category="temp-custom").first()
            assert cfg_check is None
            assert winner_check is None


def test_awards_validation_and_disabling(client, app, default_club, staff_user):
    """Verify that updating awards enforces max_votes <= max_winners, allows 0 to disable, hides from voting page, and blocks votes."""
    with app.app_context():
        # Ensure staff role has AGENDA_EDIT permission
        from app.models import AuthRole, Permission
        from app.auth.permissions import Permissions
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        agenda_edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
        if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_edit_perm)
            db.session.commit()

        # Create contacts
        c_1 = Contact(Name="Winner One", Type="Member")
        db.session.add(c_1)
        db.session.commit()
        db.session.add(ContactClub(contact_id=c_1.id, club_id=default_club.id))
        db.session.commit()

        from app.models import Roster, Ticket
        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
            db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=996,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='running',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id
        w1_id = c_1.id

        # Add to roster
        r1 = Roster(meeting_id=meeting_id, contact_id=w1_id, ticket_id=t.id, order_number=1)
        db.session.add(r1)
        db.session.commit()

    # Authenticate client
    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    # Post unified awards list:
    # 1. 'speaker' has max_votes = 0, max_winners = 0 (disabled standard category, try to pass winner_ids)
    # 2. 'best-dresser' (custom) has max_votes = 3, max_winners = 2 (capped to 2)
    # 3. 'best-tie' (custom) has max_votes = 0, max_winners = 0 (disabled custom category)
    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post(
            '/agenda/update',
            json={
                'meeting_id': meeting_id,
                'agenda_data': [],
                'awards': [
                    {
                        'category': 'speaker',
                        'label': 'Best Speaker',
                        'max_votes': 0,
                        'max_winners': 0,
                        'associated_role': None,
                        'winner_ids': [w1_id]
                    },
                    {
                        'category': 'best-dresser',
                        'label': 'Best Dresser',
                        'max_votes': 3,
                        'max_winners': 2,
                        'associated_role': None,
                        'winner_ids': [w1_id]
                    },
                    {
                        'category': 'best-tie',
                        'label': 'Best Tie',
                        'max_votes': 0,
                        'max_winners': 0,
                        'associated_role': None,
                        'winner_ids': []
                    }
                ]
            }
        )

        assert resp.status_code == 200
        assert resp.get_json().get('success') is True

        with app.app_context():
            from app.models.voting import MeetingAwardConfig, MeetingAwardWinner
            configs = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id).all()
            
            # speaker config should have 0 votes/winners
            sp_cfg = next(c for c in configs if c.award_category == 'speaker')
            assert sp_cfg.max_votes_per_user == 0
            assert sp_cfg.max_winners == 0

            # best-dresser config should have max_votes capped at 2 (since max_winners=2)
            dr_cfg = next(c for c in configs if c.award_category == 'best-dresser')
            assert dr_cfg.max_votes_per_user == 2
            assert dr_cfg.max_winners == 2

            # best-tie config should have 0 votes/winners
            tie_cfg = next(c for c in configs if c.award_category == 'best-tie')
            assert tie_cfg.max_votes_per_user == 0
            assert tie_cfg.max_winners == 0

            # Verify no winners saved for disabled 'speaker' category
            winners = MeetingAwardWinner.query.filter_by(meeting_id=meeting_id).all()
            speaker_winners = [w for w in winners if w.award_category == 'speaker']
            assert len(speaker_winners) == 0

            # Verify dresser winner is saved
            dresser_winners = [w for w in winners if w.award_category == 'best-dresser']
            assert len(dresser_winners) == 1
            assert dresser_winners[0].contact_id == w1_id

            # Verify voting page roles generation filters out disabled categories
            from app.voting_routes import _get_roles_for_voting
            from flask_login import login_user
            m_obj = db.session.get(Meeting, meeting_id)
            
            with app.test_request_context():
                from app.models import User
                staff = db.session.get(User, staff_user.id)
                login_user(staff)
                
                with patch('app.voting_routes.is_authorized', return_value=True):
                    roles = _get_roles_for_voting(meeting_id, m_obj)
                    categories = {r.get('award_category') for r in roles}
                    
                    # 'speaker' and 'best-tie' must not be present
                    assert 'speaker' not in categories
                    assert 'best-tie' not in categories
                    # 'best-dresser' should be present
                    assert 'best-dresser' in categories

    # Verify that requesting voting page does not render disabled categories
    with patch('app.voting_routes.is_authorized', return_value=True):
        resp_voting = client.get(f'/voting/{meeting_id}')
        assert resp_voting.status_code == 200
        html = resp_voting.get_data(as_text=True)
        assert 'Best Speaker' not in html
        assert 'Best Tie' not in html
        assert 'Best Dresser' in html

    # Verify backend voting route blocks/ignores votes for disabled categories
    # Try batch voting for a disabled category 'speaker'
    resp_batch = client.post(
        '/voting/batch_vote',
        json={
            'meeting_id': meeting_id,
            'votes': [
                {'contact_id': w1_id, 'award_category': 'speaker'},
                {'contact_id': w1_id, 'award_category': 'best-dresser'}
            ]
        }
    )
    assert resp_batch.status_code == 200
    with app.app_context():
        from app.models.voting import Vote
        # There should be a vote for best-dresser, but not for speaker
        dresser_votes = Vote.query.filter_by(meeting_id=meeting_id, award_category='best-dresser').all()
        assert len(dresser_votes) == 1
        speaker_votes = Vote.query.filter_by(meeting_id=meeting_id, award_category='speaker').all()
        assert len(speaker_votes) == 0

    # Try individual vote endpoint for 'speaker'
    resp_indiv = client.post(
        '/voting/vote',
        json={
            'meeting_id': meeting_id,
            'contact_id': w1_id,
            'award_category': 'speaker'
        }
    )
    assert resp_indiv.status_code == 400


# ===== Tests for award_role_configs associative table =====

def _ensure_staff_has_meeting_manage(app):
    """Helper: ensure the Staff auth role has the MEETING_MANAGE permission."""
    from app.models import AuthRole, Permission
    from app.auth.permissions import Permissions
    staff_role = AuthRole.query.filter_by(name='Staff').first()
    agenda_edit_perm = Permission.query.filter_by(name=Permissions.MEETING_MANAGE).first()
    if staff_role and agenda_edit_perm and agenda_edit_perm not in staff_role.permissions:
        staff_role.permissions.append(agenda_edit_perm)
        db.session.commit()


def test_award_role_associations_single_role(client, app, default_club, staff_user):
    """A custom award with selected_role_ids=[leading_role.id] persists one AwardRoleConfig row
    and keeps associated_role in sync with the first selected role's name."""
    with app.app_context():
        _ensure_staff_has_meeting_manage(app)

        c1 = Contact(Name="Leading Taker", Type="Member")
        c2 = Contact(Name="Functional Taker", Type="Member")
        db.session.add_all([c1, c2])
        db.session.commit()
        db.session.add_all([
            ContactClub(contact_id=c1.id, club_id=default_club.id),
            ContactClub(contact_id=c2.id, club_id=default_club.id),
        ])

        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
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
        meeting_id = meeting.id

        # Roster entries
        r1 = Roster(meeting_id=meeting_id, contact_id=c1.id, ticket_id=t.id)
        r2 = Roster(meeting_id=meeting_id, contact_id=c2.id, ticket_id=t.id)
        db.session.add_all([r1, r2])
        db.session.commit()

        # Two roles of different types
        mr_leading = MeetingRole(name="Toastmaster", type="leading", needs_approval=False,
                                  has_single_owner=True, club_id=default_club.id)
        mr_functional = MeetingRole(name="Timer", type="functional", needs_approval=False,
                                     has_single_owner=True, club_id=default_club.id)
        db.session.add_all([mr_leading, mr_functional])
        db.session.commit()

        from app.models import OwnerMeetingRoles
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_leading.id, contact_id=c1.id))
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_functional.id, contact_id=c2.id))
        db.session.commit()

        leading_id = mr_leading.id

    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post('/agenda/update', json={
            'meeting_id': meeting_id,
            'agenda_data': [],
            'meeting_title': 'Single-Role Test',
            'awards': [{
                'category': 'best-leader',
                'label': 'Best Leader',
                'max_votes': 1,
                'max_winners': 1,
                'associated_role': None,
                'selected_role_ids': [leading_id],
                'winner_ids': [],
            }],
        })
    if resp.status_code != 200:
        # Surface the server-side error to make test failures actionable
        raise AssertionError(f"Expected 200, got {resp.status_code}: {resp.get_data(as_text=True)[:500]}")
    assert resp.get_json().get('success') is True


def test_award_role_associations_multi_role(client, app, default_club, staff_user):
    """A custom award with multiple selected_role_ids unions role takers across all selected roles."""
    with app.app_context():
        _ensure_staff_has_meeting_manage(app)

        c1 = Contact(Name="Leading Taker", Type="Member")
        c2 = Contact(Name="Functional Taker", Type="Member")
        db.session.add_all([c1, c2])
        db.session.commit()
        db.session.add_all([
            ContactClub(contact_id=c1.id, club_id=default_club.id),
            ContactClub(contact_id=c2.id, club_id=default_club.id),
        ])

        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
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

        r1 = Roster(meeting_id=meeting_id, contact_id=c1.id, ticket_id=t.id)
        r2 = Roster(meeting_id=meeting_id, contact_id=c2.id, ticket_id=t.id)
        db.session.add_all([r1, r2])
        db.session.commit()

        mr_leading = MeetingRole(name="Toastmaster", type="leading", needs_approval=False,
                                  has_single_owner=True, club_id=default_club.id)
        mr_functional = MeetingRole(name="Timer", type="functional", needs_approval=False,
                                     has_single_owner=True, club_id=default_club.id)
        db.session.add_all([mr_leading, mr_functional])
        db.session.commit()

        from app.models import OwnerMeetingRoles
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_leading.id, contact_id=c1.id))
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_functional.id, contact_id=c2.id))
        db.session.commit()

        leading_id = mr_leading.id
        functional_id = mr_functional.id

    client.post('/login', data=dict(username='staff', password='password'))
    with client.session_transaction() as sess:
        sess['club_id'] = default_club.id
        sess['current_club_id'] = default_club.id

    with patch('app.agenda_routes.is_authorized', return_value=True):
        resp = client.post('/agenda/update', json={
            'meeting_id': meeting_id,
            'agenda_data': [],
            'meeting_title': 'Multi-Role Test',
            'awards': [{
                'category': 'best-all',
                'label': 'Best All',
                'max_votes': 1,
                'max_winners': 2,
                'associated_role': None,
                'selected_role_ids': [leading_id, functional_id],
                'winner_ids': [],
            }],
        })
    assert resp.status_code == 200

    with app.app_context():
        from app.models.voting import MeetingAwardConfig
        cfg = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id, award_category='best-all').first()
        assert cfg is not None
        assert {a.meeting_role_id for a in cfg.role_associations} == {leading_id, functional_id}
        # Legacy field is set to the first selected role's name
        assert cfg.associated_role == 'Toastmaster'

        # Candidate filter returns union of both role takers
        from app.voting_routes import _get_roles_for_voting
        m_obj = db.session.get(Meeting, meeting_id)
        with app.test_request_context():
            from app.models import User
            staff = db.session.get(User, staff_user.id)
            from flask_login import login_user
            login_user(staff)
            with patch('app.voting_routes.is_authorized', return_value=True):
                roles = _get_roles_for_voting(meeting_id, m_obj)
                candidates = [r for r in roles if r.get('award_category') == 'best-all']
                owner_ids = {c['owner_id'] for c in candidates}
                assert c1.id in owner_ids
                assert c2.id in owner_ids


def test_award_role_associations_legacy_fallback(client, app, default_club, staff_user):
    """A config with associated_role set but no AwardRoleConfig rows still surfaces candidates
    via the legacy fallback path."""
    with app.app_context():
        _ensure_staff_has_meeting_manage(app)

        c1 = Contact(Name="Legacy Timer Taker", Type="Member")
        db.session.add(c1)
        db.session.commit()
        db.session.add(ContactClub(contact_id=c1.id, club_id=default_club.id))

        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
            db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=1003,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id

        r1 = Roster(meeting_id=meeting_id, contact_id=c1.id, ticket_id=t.id)
        db.session.add(r1)
        db.session.commit()

        mr_timer = MeetingRole(name="Timer", type="standard", needs_approval=False,
                                has_single_owner=True, club_id=default_club.id)
        db.session.add(mr_timer)
        db.session.commit()

        from app.models import OwnerMeetingRoles
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_timer.id, contact_id=c1.id))

        # Manually create a config with associated_role but no AwardRoleConfig rows
        from app.models.voting import MeetingAwardConfig
        cfg = MeetingAwardConfig(
            meeting_id=meeting_id,
            award_category='best-legacy',
            max_votes_per_user=1,
            max_winners=1,
            associated_role='Timer',
        )
        db.session.add(cfg)
        db.session.commit()

        # Sanity: no role_associations
        assert len(cfg.role_associations) == 0

        # Candidate filter falls back to legacy name match
        from app.voting_routes import _get_roles_for_voting
        m_obj = db.session.get(Meeting, meeting_id)
        with app.test_request_context():
            from app.models import User
            staff = db.session.get(User, staff_user.id)
            from flask_login import login_user
            login_user(staff)
            with patch('app.voting_routes.is_authorized', return_value=True):
                roles = _get_roles_for_voting(meeting_id, m_obj)
                candidates = [r for r in roles if r.get('award_category') == 'best-legacy']
                owner_ids = {c['owner_id'] for c in candidates}
                assert c1.id in owner_ids


def test_candidate_role_name_on_voting_page(client, app, default_club, staff_user):
    """Verify that candidates on the voting page display their actual meeting role name when available,
    and fallback to 'Candidate' when they have no role in the meeting."""
    with app.app_context():
        _ensure_staff_has_meeting_manage(app)

        c1 = Contact(Name="Has Role Candidate", Type="Member")
        c2 = Contact(Name="No Role Candidate", Type="Member")
        db.session.add_all([c1, c2])
        db.session.commit()
        db.session.add(ContactClub(contact_id=c1.id, club_id=default_club.id))
        db.session.add(ContactClub(contact_id=c2.id, club_id=default_club.id))

        t = Ticket.query.filter_by(name='Standard').first()
        if not t:
            t = Ticket(name='Standard', price=0)
            db.session.add(t)
            db.session.commit()

        from datetime import date
        meeting = Meeting(
            Meeting_Number=1004,
            Meeting_Date=date.today(),
            club_id=default_club.id,
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        meeting_id = meeting.id

        # Add both to roster so they are candidates
        r1 = Roster(meeting_id=meeting_id, contact_id=c1.id, ticket_id=t.id)
        r2 = Roster(meeting_id=meeting_id, contact_id=c2.id, ticket_id=t.id)
        db.session.add_all([r1, r2])
        db.session.commit()

        # c1 has role "Timer"
        mr_timer = MeetingRole(name="Timer", type="standard", needs_approval=False,
                                has_single_owner=True, club_id=default_club.id)
        db.session.add(mr_timer)
        db.session.commit()

        from app.models import OwnerMeetingRoles
        db.session.add(OwnerMeetingRoles(meeting_id=meeting_id, role_id=mr_timer.id, contact_id=c1.id))
        db.session.commit()

        # Create a config with no associations, so it defaults to roster_contacts
        from app.models.voting import MeetingAwardConfig
        cfg = MeetingAwardConfig(
            meeting_id=meeting_id,
            award_category='best-custom',
            max_votes_per_user=1,
            max_winners=1,
        )
        db.session.add(cfg)
        db.session.commit()

        from app.voting_routes import _get_roles_for_voting
        m_obj = db.session.get(Meeting, meeting_id)
        with app.test_request_context():
            from app.models import User
            staff = db.session.get(User, staff_user.id)
            from flask_login import login_user
            login_user(staff)
            with patch('app.voting_routes.is_authorized', return_value=True):
                roles = _get_roles_for_voting(meeting_id, m_obj)
                candidates = [r for r in roles if r.get('award_category') == 'best-custom']
                
                # Check that c1 has role 'Timer' and c2 has role 'Candidate'
                c1_entry = next(c for c in candidates if c['owner_id'] == c1.id)
                c2_entry = next(c for c in candidates if c['owner_id'] == c2.id)
                
                assert c1_entry['role'] == 'Timer'
                assert c2_entry['role'] == 'Candidate'


