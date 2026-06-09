"""Tests for the Self Check-In feature (app/checkin_routes.py + officer
endpoints in app/roster_routes.py + token helpers)."""
from datetime import date

import pytest

from app import db
from app.models import (
    Club, ClubModule, Contact, Meeting, Roster, Ticket, AuthRole, User,
    UserClub, Permission,
)
from app.auth.permissions import Permissions
from app.services.checkin_service import generate_checkin_token, verify_checkin_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def checkin_club(app):
    with app.app_context():
        club = Club.query.first()
        if not club:
            club = Club(club_no='000001', club_name='Check-In Club')
            db.session.add(club)
            db.session.commit()
        # Enable the Self Check-In module for this club.
        mod = ClubModule.query.filter_by(club_id=club.id, module_name='Self Check-In').first()
        if not mod:
            mod = ClubModule(club_id=club.id, module_name='Self Check-In', is_enabled=True)
            db.session.add(mod)
        else:
            mod.is_enabled = True
        db.session.commit()
        return club


@pytest.fixture
def active_meeting(app, checkin_club):
    with app.app_context():
        meeting = Meeting(
            club_id=checkin_club.id,
            Meeting_Number=1,
            Meeting_Date=date(2026, 6, 10),
            Meeting_Title='Test Meeting',
            status='not started',
        )
        db.session.add(meeting)
        db.session.commit()
        return meeting


@pytest.fixture
def finished_meeting(app, checkin_club):
    with app.app_context():
        meeting = Meeting(
            club_id=checkin_club.id,
            Meeting_Number=2,
            Meeting_Date=date(2026, 6, 10),
            Meeting_Title='Past Meeting',
            status='finished',
        )
        db.session.add(meeting)
        db.session.commit()
        return meeting


@pytest.fixture
def roster_entry(app, active_meeting, checkin_club):
    with app.app_context():
        ticket = Ticket(name='Walk-in', type='Guest', price=0.0, club_id=checkin_club.id)
        db.session.add(ticket)
        db.session.flush()
        contact = Contact(Name='Alice Guest', Type='Guest')
        db.session.add(contact)
        db.session.flush()
        entry = Roster(
            meeting_id=active_meeting.id,
            contact_id=contact.id,
            ticket_id=ticket.id,
            contact_type='Guest',
        )
        db.session.add(entry)
        db.session.commit()
        return entry


@pytest.fixture
def officer_user(app, checkin_club, seeded_permissions):
    """A user with ROSTER_EDIT in checkin_club."""
    with app.app_context():
        user = User.query.filter_by(username='officer').first()
        if user:
            return user
        user = User(username='officer', email='officer@example.com', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        role = AuthRole.query.filter_by(name='Operator').first()
        if not role:
            role = AuthRole(name='Operator', level=3)
            db.session.add(role)
            db.session.flush()
        # Grant ROSTER_EDIT (and a couple of related perms) via the role.
        for perm_name in (Permissions.ROSTER_EDIT, Permissions.ROSTER_VIEW, Permissions.MEETING_VIEW_PUBLISHED):
            perm = Permission.query.filter_by(name=perm_name).first()
            if perm and perm not in role.permissions:
                role.permissions.append(perm)
        user.roles.append(role)

        uc = UserClub(user_id=user.id, club_id=checkin_club.id, club_role_level=role.level)
        db.session.add(uc)
        db.session.commit()
        return user


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def test_token_round_trip(app):
    with app.app_context():
        token = generate_checkin_token(42)
        assert verify_checkin_token(token) == 42


def test_expired_token_returns_none(app):
    with app.app_context():
        token = generate_checkin_token(7)
        # max_age=0 forces SignatureExpired on the very next tick.
        assert verify_checkin_token(token, max_age=-1) is None


def test_garbage_token_returns_none(app):
    with app.app_context():
        assert verify_checkin_token('not-a-real-token') is None


# ---------------------------------------------------------------------------
# Public GET /checkin/<token>
# ---------------------------------------------------------------------------

def test_get_page_renders_for_active_meeting(app, client, active_meeting, roster_entry):
    with app.app_context():
        token = generate_checkin_token(active_meeting.id)
        resp = client.get(f'/checkin/{token}')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'Alice Guest' in body


def test_get_page_404_for_finished_meeting(app, client, finished_meeting):
    with app.app_context():
        token = generate_checkin_token(finished_meeting.id)
        resp = client.get(f'/checkin/{token}')
        assert resp.status_code == 404


def test_get_page_404_for_garbage_token(app, client, checkin_club):
    with app.app_context():
        resp = client.get('/checkin/totally-bogus-token')
        assert resp.status_code == 404


def test_get_page_404_when_module_disabled(app, client, active_meeting, roster_entry, checkin_club):
    with app.app_context():
        mod = ClubModule.query.filter_by(club_id=checkin_club.id, module_name='Self Check-In').first()
        mod.is_enabled = False
        db.session.commit()
        token = generate_checkin_token(active_meeting.id)
        resp = client.get(f'/checkin/{token}')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Public POST /checkin/<token>/mark/<roster_id>
# ---------------------------------------------------------------------------

def test_post_mark_sets_timestamp(app, client, active_meeting, roster_entry):
    with app.app_context():
        token = generate_checkin_token(active_meeting.id)
        resp = client.post(f'/checkin/{token}/mark/{roster_entry.id}',
                            json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['already'] is False
        assert data['checked_in_at'] is not None
        assert data['checked_in_via'] == 'self'

        # Reload and confirm persisted.
        refreshed = db.session.get(Roster, roster_entry.id)
        assert refreshed.checked_in_at is not None
        assert refreshed.checked_in_via == 'self'
        assert refreshed.checked_in_by_user_id is None


def test_post_mark_idempotent(app, client, active_meeting, roster_entry):
    with app.app_context():
        token = generate_checkin_token(active_meeting.id)
        first = client.post(f'/checkin/{token}/mark/{roster_entry.id}', json={}).get_json()
        second = client.post(f'/checkin/{token}/mark/{roster_entry.id}', json={}).get_json()
        assert second['success'] is True
        assert second['already'] is True
        assert second['checked_in_at'] == first['checked_in_at']


def test_post_mark_cross_meeting_replay_404(app, client, active_meeting, finished_meeting, roster_entry):
    """Token for meeting A cannot mark a roster row from meeting B."""
    with app.app_context():
        # Create a row in finished_meeting; token for active_meeting must reject it.
        other_entry = Roster(meeting_id=finished_meeting.id, contact_id=roster_entry.contact_id)
        db.session.add(other_entry)
        db.session.commit()
        token = generate_checkin_token(active_meeting.id)
        resp = client.post(f'/checkin/{token}/mark/{other_entry.id}', json={})
        assert resp.status_code == 404


def test_post_mark_404_when_module_disabled(app, client, active_meeting, roster_entry, checkin_club):
    with app.app_context():
        mod = ClubModule.query.filter_by(club_id=checkin_club.id, module_name='Self Check-In').first()
        mod.is_enabled = False
        db.session.commit()
        token = generate_checkin_token(active_meeting.id)
        resp = client.post(f'/checkin/{token}/mark/{roster_entry.id}', json={})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Officer-side endpoints in roster_routes.py
# ---------------------------------------------------------------------------

def test_officer_qr_endpoint_requires_login(app, client, active_meeting):
    """Anonymous users get bounced to login (302), not 200."""
    with app.app_context():
        resp = client.get(f'/roster/api/checkin/qr/{active_meeting.id}')
        assert resp.status_code in (302, 401, 403)


def test_officer_qr_endpoint_returns_png_with_permission(app, client, auth, officer_user,
                                                          checkin_club, active_meeting):
    with app.app_context():
        auth.login(username='officer', password='password', club_id=checkin_club.id)
        resp = client.get(f'/roster/api/checkin/qr/{active_meeting.id}')
        assert resp.status_code == 200
        assert resp.mimetype == 'image/png'
        assert resp.data[:8] == b'\x89PNG\r\n\x1a\n'


def test_officer_url_endpoint_returns_signed_token(app, client, auth, officer_user,
                                                    checkin_club, active_meeting):
    with app.app_context():
        auth.login(username='officer', password='password', club_id=checkin_club.id)
        resp = client.get(f'/roster/api/checkin/url/{active_meeting.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'url' in data and 'token' in data
        # Token must decode back to this meeting.
        assert verify_checkin_token(data['token']) == active_meeting.id


def test_officer_toggle_sets_and_clears(app, client, auth, officer_user,
                                         checkin_club, active_meeting, roster_entry):
    with app.app_context():
        auth.login(username='officer', password='password', club_id=checkin_club.id)
        resp = client.post(f'/roster/api/entry/{roster_entry.id}/checkin')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['checked_in_at'] is not None
        assert data['checked_in_via'] == 'officer'
        assert data['checked_in_by'] is not None

        refreshed = db.session.get(Roster, roster_entry.id)
        assert refreshed.checked_in_by_user_id == officer_user.id

        # Second call should clear (undo).
        resp = client.post(f'/roster/api/entry/{roster_entry.id}/checkin')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['checked_in_at'] is None
        assert data['checked_in_via'] is None
        assert data['checked_in_by'] is None
