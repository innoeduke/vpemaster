"""Verify that role-mode save (changing owner on a Timer-style role) does
not clear the session title in the database."""
from unittest.mock import patch
from app.models import db, Contact, Project, SessionLog, SessionType, Meeting, MeetingRole, OwnerMeetingRoles, ContactClub
from datetime import date


def test_role_mode_save_preserves_title(client, app, default_club, staff_user):
    with app.app_context():
        # Single-owner functional role (Timer)
        role = MeetingRole(name="TimerRole", type="standard",
                            needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Timer", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        alice = Contact(Name="Alice", Type="Member", Current_Path="Dynamic Leadership")
        bob = Contact(Name="Bob", Type="Member", Current_Path="Engaging Humor")
        db.session.add_all([alice, bob])
        db.session.commit()
        for c in (alice, bob):
            db.session.add(ContactClub(contact_id=c.id, club_id=default_club.id))
        db.session.commit()

        meeting = Meeting(Meeting_Number=9010, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        original_title = "Original Timer Title"
        log = SessionLog(meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st.id,
                         Status="Booked", Session_Title=original_title)
        db.session.add(log)
        db.session.flush()
        log.owners = [alice]
        db.session.commit()

        log_id = log.id
        bob_id = bob.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(staff_user.id)
        sess["club_id"] = default_club.id
        sess["_fresh"] = True

    payload = {
        "owner_ids": [str(bob_id)],
        "owner_targets": {str(bob_id): {"pathway": "Non Pathway", "level": ""}},
        "session_title": original_title,
    }
    with patch("app.speech_logs_routes.is_authorized", return_value=True):
        resp = client.post(f"/speech_log/update/{log_id}", json=payload)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.data.decode()}"
    data = resp.get_json()
    assert data.get("success") is True

    with app.app_context():
        from app.models import SessionLog as SL
        updated = db.session.get(SL, log_id)
        assert updated.Session_Title == original_title, (
            f"Title was cleared/changed: expected {original_title!r}, got {updated.Session_Title!r}"
        )


def test_multi_owner_role_mode_save_preserves_title(client, app, default_club, staff_user):
    """The user's reported case: a multi-owner role (has_single_owner=False),
    change one of the owners, title should be preserved."""
    with app.app_context():
        role = MeetingRole(name="VotingRole", type="club-specific",
                            needs_approval=False, has_single_owner=False)
        db.session.add(role)
        db.session.commit()

        st = SessionType(Title="Ballot Counter", role_id=role.id, club_id=default_club.id)
        db.session.add(st)
        db.session.commit()

        alice = Contact(Name="Alice", Type="Member", Current_Path="Dynamic Leadership")
        bob = Contact(Name="Bob", Type="Member", Current_Path="Engaging Humor")
        carol = Contact(Name="Carol", Type="Member", Current_Path="Visionary Communication")
        db.session.add_all([alice, bob, carol])
        db.session.commit()
        for c in (alice, bob, carol):
            db.session.add(ContactClub(contact_id=c.id, club_id=default_club.id))
        db.session.commit()

        meeting = Meeting(Meeting_Number=9011, Meeting_Date=date.today(), club_id=default_club.id)
        db.session.add(meeting)
        db.session.commit()

        original_title = "Original Ballot Counter Title"
        log = SessionLog(meeting_id=meeting.id, Meeting_Seq=1, Type_ID=st.id,
                         Status="Booked", Session_Title=original_title)
        db.session.add(log)
        db.session.flush()
        log.owners = [alice, bob]
        db.session.commit()

        # OMRs to mirror what the role service would have created
        for c in (alice, bob):
            db.session.add(OwnerMeetingRoles(meeting_id=meeting.id, role_id=role.id, contact_id=c.id))
        db.session.commit()

        log_id = log.id
        carol_id = carol.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(staff_user.id)
        sess["club_id"] = default_club.id
        sess["_fresh"] = True

    # Replace Alice with Carol, keep Bob
    payload = {
        "owner_ids": [str(carol_id), str(bob.id)],
        "owner_targets": {
            str(carol_id): {"pathway": "Visionary Communication", "level": "1"},
            str(bob.id): {"pathway": "Engaging Humor", "level": "1"},
        },
        "session_title": original_title,
    }
    with patch("app.speech_logs_routes.is_authorized", return_value=True):
        resp = client.post(f"/speech_log/update/{log_id}", json=payload)
    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.data.decode()}"
    data = resp.get_json()
    assert data.get("success") is True

    with app.app_context():
        from app.models import SessionLog as SL
        updated = db.session.get(SL, log_id)
        assert updated.Session_Title == original_title, (
            f"Title was cleared/changed: expected {original_title!r}, got {updated.Session_Title!r}"
        )
