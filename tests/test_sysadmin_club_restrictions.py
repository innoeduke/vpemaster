"""
Tests that enforce the sysadmin account is only a member of the super club.

The sysadmin account (username == 'sysadmin') must:
  - only ever have a UserClub in the super club (id = GLOBAL_CLUB_ID)
  - never see Join / Cancel Request / Quit / Cancel Quit controls in the
    club directory
  - have every code path that would add it to a normal club return an error
"""
import pytest

from app.constants import GLOBAL_CLUB_ID
from app.models import Club, User, UserClub, AuthRole, Message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sysadmin_user(app, default_club):
    """Create a sysadmin user linked to the super club (GLOBAL_CLUB_ID)."""
    from app.models import db
    with app.app_context():
        # default_club is the first club created in a fresh DB and thus has
        # id == GLOBAL_CLUB_ID. Use it as the super club.
        super_club = db.session.get(Club, GLOBAL_CLUB_ID) or default_club

        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_restrict@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()

        # Ensure a UserClub exists linking sysadmin to the super club only.
        existing = UserClub.query.filter_by(user_id=sysadmin.id).all()
        for uc in existing:
            db.session.delete(uc)
        db.session.flush()

        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        if not sysadmin_role:
            sysadmin_role = AuthRole(name='SysAdmin', level=100)
            db.session.add(sysadmin_role)
            db.session.flush()

        uc = UserClub(
            user_id=sysadmin.id,
            club_id=super_club.id,
            club_role_level=sysadmin_role.level,
            is_home=True,
        )
        db.session.add(uc)
        db.session.commit()
        db.session.refresh(sysadmin)
        return sysadmin


@pytest.fixture
def normal_club(app, default_club):
    """Create a normal (non-super) club for testing restrictions.

    Depends on ``default_club`` so the super club occupies id=1 and this
    fixture's club gets the next id (id != GLOBAL_CLUB_ID).
    """
    from app.models import db
    with app.app_context():
        # Make sure there's at least one non-super club to target.
        club = Club.query.filter(Club.id != GLOBAL_CLUB_ID).first()
        if not club:
            club = Club(
                club_no='999001',
                club_name='Normal Test Club',
                district='00',
            )
            db.session.add(club)
            db.session.commit()
            db.session.refresh(club)
        return club


@pytest.fixture
def login_sysadmin(client, sysadmin_user):
    """Log in the sysadmin fixture via the test client's session."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True
    return client


# ---------------------------------------------------------------------------
# UI: join button hidden
# ---------------------------------------------------------------------------

def test_join_button_hidden_for_sysadmin(login_sysadmin, app, normal_club):
    """Sysadmin must not see Join, Cancel Request, Quit, or Cancel Quit buttons.

    The CSS class names ``btn-join`` / ``btn-quit`` / ``btn-cancel-request``
    appear in the <style> block and in JS string literals that re-render the
    buttons after an AJAX response. The actual rendered buttons carry a
    numeric ``club.id`` in their onclick handler (e.g.
    ``onclick="requestJoinClub(this, 123)"``) while the JS string literal
    uses ``' + clubId + '``. We match the rendered-button pattern only.
    """
    import re

    response = login_sysadmin.get('/clubs')
    assert response.status_code == 200
    body = response.data.decode('utf-8')

    assert not re.search(
        r'<button class="btn-join"\s+onclick="requestJoinClub\(this, \d+\)"',
        body,
    )
    assert not re.search(
        r'<button class="btn-quit"\s+onclick="requestQuitClub\(this, \d+\)"',
        body,
    )
    assert not re.search(
        r'<button class="btn-cancel-request"\s+onclick="cancelJoinRequest\(this, \d+\)"',
        body,
    )
    assert not re.search(
        r'<button class="btn-cancel-request"\s+onclick="cancelQuitRequest\(this, \d+\)"',
        body,
    )


def test_join_button_visible_for_regular_user(client, app, normal_club):
    """Sanity check: a regular user who is NOT a member of normal_club still
    sees the Join button."""
    from app.models import db
    with app.app_context():
        role = AuthRole.query.filter_by(name='Member').first()
        if not role:
            role = AuthRole(name='Member', level=1)
            db.session.add(role)
            db.session.flush()

        user = User.query.filter_by(username='regular_member').first()
        if not user:
            user = User(username='regular_member', email='regular_member@test.com')
            user.set_password('password')
            db.session.add(user)
            db.session.flush()

        super_club = db.session.get(Club, GLOBAL_CLUB_ID)
        # Member of the super club (so login context works), but NOT of normal_club.
        if not UserClub.query.filter_by(user_id=user.id, club_id=super_club.id).first():
            db.session.add(UserClub(user_id=user.id, club_id=super_club.id, club_role_level=role.level))
        UserClub.query.filter_by(user_id=user.id, club_id=normal_club.id).delete()
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True

    response = client.get('/clubs')
    assert response.status_code == 200
    body = response.data.decode('utf-8')
    import re
    assert re.search(
        r'<button class="btn-join"\s+onclick="requestJoinClub\(this, \d+\)"',
        body,
    ), "Expected an actual rendered join button for a non-member user"


# ---------------------------------------------------------------------------
# Route-level rejections
# ---------------------------------------------------------------------------

def test_request_join_rejected_for_sysadmin(login_sysadmin, normal_club):
    response = login_sysadmin.post(f'/clubs/{normal_club.id}/request_join')
    assert response.status_code == 400
    assert response.json['success'] is False
    assert 'super club' in response.json['error'].lower()


def test_request_quit_rejected_for_sysadmin(login_sysadmin, normal_club):
    response = login_sysadmin.post(f'/clubs/{normal_club.id}/request_quit')
    assert response.status_code == 400
    assert response.json['success'] is False
    assert 'super club' in response.json['error'].lower()


def test_cancel_join_rejected_for_sysadmin(login_sysadmin, normal_club):
    response = login_sysadmin.post(f'/clubs/{normal_club.id}/cancel_join')
    assert response.status_code == 400
    assert response.json['success'] is False


def test_cancel_quit_rejected_for_sysadmin(login_sysadmin, normal_club):
    response = login_sysadmin.post(f'/clubs/{normal_club.id}/cancel_quit')
    assert response.status_code == 400
    assert response.json['success'] is False


# ---------------------------------------------------------------------------
# enter_club must not create a UserClub for sysadmin in a normal club
# ---------------------------------------------------------------------------

def test_enter_normal_club_does_not_create_userclub(login_sysadmin, app, normal_club, sysadmin_user):
    response = login_sysadmin.post(f'/clubs/{normal_club.id}/enter')
    assert response.status_code == 200
    assert response.json['success'] is True

    with app.app_context():
        uc = UserClub.query.filter_by(user_id=sysadmin_user.id, club_id=normal_club.id).first()
        assert uc is None


def test_enter_super_club_still_works_for_sysadmin(login_sysadmin, app, sysadmin_user):
    response = login_sysadmin.post(f'/clubs/{GLOBAL_CLUB_ID}/enter')
    assert response.status_code == 200
    assert response.json['success'] is True

    # The existing super-club membership is preserved (and no duplicate is made).
    with app.app_context():
        ucs = UserClub.query.filter_by(user_id=sysadmin_user.id, club_id=GLOBAL_CLUB_ID).all()
        assert len(ucs) == 1


# ---------------------------------------------------------------------------
# respond_join_request must not let an admin add sysadmin to a normal club
# ---------------------------------------------------------------------------

def test_respond_join_request_rejects_sysadmin_as_requestor(app, normal_club):
    """If someone (a regular user) accidentally files a join request FROM
    sysadmin via the public flow, the approval must not link sysadmin into
    that club."""
    from app.models import db
    with app.app_context():
        # Seed sysadmin in super club.
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_resp@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()
        super_club = db.session.get(Club, GLOBAL_CLUB_ID)

        if not UserClub.query.filter_by(user_id=sysadmin.id, club_id=super_club.id).first():
            db.session.add(UserClub(user_id=sysadmin.id, club_id=super_club.id, is_home=True))

        # An admin in the normal club.
        admin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not admin_role:
            admin_role = AuthRole(name='ClubAdmin', level=2)
            db.session.add(admin_role)
            db.session.flush()

        # Give the admin role SETTINGS_EDIT so it passes the auth check
        # inside respond_join_request and we exercise the sysadmin guard.
        from app.auth.permissions import Permissions
        from app.models import Permission, RolePermission
        edit_perm = Permission.query.filter_by(name=Permissions.SETTINGS_EDIT).first()
        if not edit_perm:
            edit_perm = Permission(name=Permissions.SETTINGS_EDIT, category='settings')
            db.session.add(edit_perm)
            db.session.flush()
        existing_rp = RolePermission.query.filter_by(
            role_id=admin_role.id, permission_id=edit_perm.id, club_id=None,
        ).first()
        if not existing_rp:
            db.session.add(RolePermission(role_id=admin_role.id, permission_id=edit_perm.id, club_id=None))
            db.session.flush()

        admin = User.query.filter_by(username='normal_admin').first()
        if not admin:
            admin = User(username='normal_admin', email='normal_admin@test.com')
            admin.set_password('password')
            db.session.add(admin)
            db.session.flush()
        if not UserClub.query.filter_by(user_id=admin.id, club_id=normal_club.id).first():
            db.session.add(UserClub(user_id=admin.id, club_id=normal_club.id, club_role_level=admin_role.level))
        db.session.commit()
        AuthRole.clear_role_cache()

        # Forge a JOIN_REQUEST message from sysadmin to the admin.
        msg = Message(
            sender_id=sysadmin.id,
            recipient_id=admin.id,
            subject='Join Request',
            body=(
                f'User {sysadmin.display_name} requested to join {normal_club.club_name}.\n'
                f'\n[JOIN_REQUEST:{sysadmin.id}:{normal_club.id}]'
            ),
        )
        db.session.add(msg)
        db.session.commit()
        msg_id = msg.id
        admin_id = admin.id

    # Log in as the admin and approve the request.
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    response = client.post(
        '/clubs/respond_join_request',
        json={'message_id': msg_id, 'action': 'approve'},
    )
    assert response.status_code == 400
    assert 'super club' in response.json['error'].lower()

    with app.app_context():
        uc = UserClub.query.filter_by(user_id=sysadmin.id, club_id=normal_club.id).first()
        assert uc is None


# ---------------------------------------------------------------------------
# respond_join (invitation) must not add sysadmin to a normal club
# ---------------------------------------------------------------------------

def test_respond_join_rejects_sysadmin_as_invitee(app, normal_club):
    """If a regular user invites sysadmin to join a normal club, sysadmin
    accepting that invite must not create a UserClub."""
    from app.models import db
    with app.app_context():
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_invite@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()
        super_club = db.session.get(Club, GLOBAL_CLUB_ID)
        if not UserClub.query.filter_by(user_id=sysadmin.id, club_id=super_club.id).first():
            db.session.add(UserClub(user_id=sysadmin.id, club_id=super_club.id, is_home=True))

        inviter = User.query.filter_by(username='inviter').first()
        if not inviter:
            inviter = User(username='inviter', email='inviter@test.com')
            inviter.set_password('password')
            db.session.add(inviter)
            db.session.flush()

        msg = Message(
            sender_id=inviter.id,
            recipient_id=sysadmin.id,
            subject='Join invite',
            body=f'Please join {normal_club.club_name}.\n[CLUB_ID:{normal_club.id}]',
        )
        db.session.add(msg)
        db.session.commit()
        msg_id = msg.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin.id)
        sess['_fresh'] = True

    response = client.post(
        '/user/respond_join',
        json={'message_id': msg_id, 'action': 'join'},
    )
    assert response.status_code == 400
    assert 'super club' in response.json['error'].lower()

    with app.app_context():
        uc = UserClub.query.filter_by(user_id=sysadmin.id, club_id=normal_club.id).first()
        assert uc is None


# ---------------------------------------------------------------------------
# request_join (sysadmin inviting others) — must still work
# ---------------------------------------------------------------------------

def test_request_join_still_works_for_sysadmin_inviting_others(app, normal_club):
    """Regression guard: blocking sysadmin's *own* club membership must not
    prevent sysadmin from adding other users to a club."""
    from app.models import db
    with app.app_context():
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_inv@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()
        super_club = db.session.get(Club, GLOBAL_CLUB_ID)
        if not UserClub.query.filter_by(user_id=sysadmin.id, club_id=super_club.id).first():
            db.session.add(UserClub(user_id=sysadmin.id, club_id=super_club.id, is_home=True))

        target = User.query.filter_by(username='invite_target').first()
        if not target:
            target = User(username='invite_target', email='invite_target@test.com')
            target.set_password('password')
            db.session.add(target)
            db.session.flush()
        db.session.commit()
        target_id = target.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin.id)
        sess['_fresh'] = True

    response = client.post(
        '/user/request_join',
        json={'target_user_id': target_id, 'club_id': normal_club.id},
    )
    assert response.status_code == 200
    assert response.json['success'] is True
    assert response.json.get('direct_add') is True

    with app.app_context():
        uc = UserClub.query.filter_by(user_id=target_id, club_id=normal_club.id).first()
        assert uc is not None


# ---------------------------------------------------------------------------
# Model-level guards
# ---------------------------------------------------------------------------

def test_set_club_role_model_guard_for_sysadmin(app, normal_club):
    """User.set_club_role must silently no-op for sysadmin on a non-super club."""
    from app.models import db
    with app.app_context():
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_set@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()

        member_role = AuthRole.query.filter_by(name='Member').first()
        if not member_role:
            member_role = AuthRole(name='Member', level=1)
            db.session.add(member_role)
            db.session.flush()

        sysadmin.set_club_role(normal_club.id, role_id=member_role.id)
        db.session.commit()

        uc = UserClub.query.filter_by(user_id=sysadmin.id, club_id=normal_club.id).first()
        assert uc is None


def test_set_home_club_model_guard_for_sysadmin(app, normal_club):
    """User.set_home_club must not move sysadmin's home to a normal club."""
    from app.models import db
    with app.app_context():
        sysadmin = User.query.filter_by(username='sysadmin').first()
        if not sysadmin:
            sysadmin = User(username='sysadmin', email='sysadmin_home@test.com')
            sysadmin.set_password('password')
            db.session.add(sysadmin)
            db.session.flush()

        super_club = db.session.get(Club, GLOBAL_CLUB_ID)
        if not UserClub.query.filter_by(user_id=sysadmin.id, club_id=super_club.id).first():
            db.session.add(UserClub(user_id=sysadmin.id, club_id=super_club.id, is_home=True))
            db.session.flush()

        sysadmin.set_home_club(normal_club.id)
        db.session.commit()

        # The super-club membership is preserved (no set_home_club call moved
        # anything). Importantly, no row is created in the normal club.
        uc_normal = UserClub.query.filter_by(user_id=sysadmin.id, club_id=normal_club.id).first()
        assert uc_normal is None