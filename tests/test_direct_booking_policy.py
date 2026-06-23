"""Tests for the direct_booking_approval ClubRule policy.

When the policy is OFF, roles with MeetingRole.needs_approval=True are
directly bookable. The policy must NOT bypass the "slot already taken"
gate — a second user arriving for an occupied slot still joins the
waitlist. The cancel→auto-promote path also reflects the policy.
"""
import unittest
from datetime import date

from app import create_app, db
from app.models import Club, Contact, Meeting, SessionLog, SessionType, Waitlist
from app.models.club_rule import ClubRule
from app.models.roster import MeetingRole
from app.services.role_service import RoleService
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class TestDirectBookingPolicy(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District',
        )
        db.session.add(self.club)
        db.session.commit()

        self.meeting = Meeting(
            Meeting_Number=1,
            Meeting_Date=date.today(),
            status='running',
            club_id=self.club.id,
        )
        db.session.add(self.meeting)

        self.contact1 = Contact(Name='Alice', Email='alice@example.com')
        self.contact2 = Contact(Name='Bob', Email='bob@example.com')
        db.session.add_all([self.contact1, self.contact2])

        # A high-priority role that requires VPE approval by default.
        self.role_tm = MeetingRole(
            name='Toastmaster',
            type='meeting',
            needs_approval=True,
            has_single_owner=True,
            is_member_only=False,
        )
        # A second, normal role that doesn't require approval, used to
        # confirm the policy doesn't affect unrelated roles.
        self.role_other = MeetingRole(
            name='Timer',
            type='meeting',
            needs_approval=False,
            has_single_owner=True,
            is_member_only=False,
        )
        db.session.add_all([self.role_tm, self.role_other])
        db.session.commit()

        self.tm_type = SessionType(role_id=self.role_tm.id, Title='Toastmaster')
        self.other_type = SessionType(role_id=self.role_other.id, Title='Timer')
        db.session.add_all([self.tm_type, self.other_type])
        db.session.commit()

        self.log_tm = SessionLog(
            meeting_id=self.meeting.id,
            Type_ID=self.tm_type.id,
            Meeting_Number=self.meeting.Meeting_Number,
        )
        self.log_other = SessionLog(
            meeting_id=self.meeting.id,
            Type_ID=self.other_type.id,
            Meeting_Number=self.meeting.Meeting_Number,
        )
        db.session.add_all([self.log_tm, self.log_other])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    # ---- book_meeting_role: approval gate ----------------------

    def test_no_rule_row_means_approval_required(self):
        """Without a ClubRule row the default behavior holds: needs_approval routes to waitlist."""
        success, msg = RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertIn('waitlist', msg.lower())

        wl = Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact1.id
        ).first()
        self.assertIsNotNone(wl)

    def test_policy_explicitly_on_keeps_approval_required(self):
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=True,
        ))
        db.session.commit()

        success, msg = RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertIn('waitlist', msg.lower())

    def test_policy_off_directly_books_needs_approval_role(self):
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=False,
        ))
        db.session.commit()

        success, msg = RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertNotIn('waitlist', msg.lower())

        # Alice is the owner of the slot, not on the waitlist.
        self.assertEqual(self.log_tm.owner.id, self.contact1.id)
        wl = Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact1.id
        ).first()
        self.assertIsNone(wl)

    def test_policy_off_but_slot_taken_still_uses_waitlist(self):
        """Direct booking only applies to free slots. A second user for an
        already-booked slot still joins the waitlist and still needs VPE
        approval, even with the policy off."""
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=False,
        ))
        db.session.commit()

        # Alice takes the slot directly (policy is off, slot is free).
        success, _ = RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)

        # Bob arrives second for the same role. The slot is taken, so the
        # "already taken" gate fires — Bob must waitlist, regardless of policy.
        success, msg = RoleService.book_meeting_role(self.log_tm, self.contact2.id)
        self.assertTrue(success)
        self.assertIn('waitlist', msg.lower())

        wl = Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact2.id
        ).first()
        self.assertIsNotNone(wl)

        # And Alice is still the owner — Bob did not displace her.
        self.assertEqual(self.log_tm.owner.id, self.contact1.id)

    def test_policy_irrelevant_for_role_without_needs_approval(self):
        """A role with needs_approval=False is always directly bookable,
        even if the policy is somehow ON (it's a no-op for these roles)."""
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=True,
        ))
        db.session.commit()

        success, msg = RoleService.book_meeting_role(self.log_other, self.contact1.id)
        self.assertTrue(success)
        self.assertNotIn('waitlist', msg.lower())
        self.assertEqual(self.log_other.owner.id, self.contact1.id)

    # ---- cancel_meeting_role: auto-promote gate -----------------

    def test_cancel_does_not_promote_when_policy_on(self):
        """With approval required, cancelling a role does not auto-promote
        the waitlist — the VPE must still approve explicitly."""
        # Alice takes the slot via direct assignment (we'll bypass the
        # approval gate for the OWNER by using _captured_assign_role, then
        # join Bob to the waitlist through the normal path).
        RoleService._captured_assign_role(self.log_tm, [self.contact1.id])
        RoleService.join_waitlist(self.log_tm, self.contact2.id)

        # Sanity: Bob is on the waitlist, not the owner.
        self.assertEqual(self.log_tm.owner.id, self.contact1.id)
        self.assertIsNotNone(Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact2.id
        ).first())

        # Policy is ON by default (no rule row). Cancellation must not promote.
        success, msg = RoleService.cancel_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertNotIn('promoted', msg.lower())

        # Slot is empty; Bob is still on the waitlist (needs VPE approval).
        self.assertEqual(len(self.log_tm.owners), 0)
        self.assertIsNotNone(Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact2.id
        ).first())

    def test_cancel_auto_promotes_when_policy_off(self):
        """With direct booking enabled, cancelling a role auto-promotes the
        next waitlist entry — the VPE gate is gone for this club."""
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=False,
        ))
        db.session.commit()

        RoleService._captured_assign_role(self.log_tm, [self.contact1.id])
        RoleService.join_waitlist(self.log_tm, self.contact2.id)

        success, msg = RoleService.cancel_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertIn('promoted', msg.lower())

        # Bob is now the owner and no longer on the waitlist.
        self.assertEqual(self.log_tm.owner.id, self.contact2.id)
        self.assertIsNone(Waitlist.query.filter_by(
            session_log_id=self.log_tm.id, contact_id=self.contact2.id
        ).first())

    # ---- annotate_effective_needs_approval (UI side) -----------

    def _make_role_dicts(self):
        """Build a tiny list of role dicts the way get_meeting_roles would."""
        return [
            {'role': 'Toastmaster', 'needs_approval': True,
             'session_id': self.log_tm.id},
            {'role': 'Timer', 'needs_approval': False,
             'session_id': self.log_other.id},
        ]

    def test_annotate_default_policy_keeps_needs_approval(self):
        """No ClubRule row: effective == raw (policy defaults to ON)."""
        roles = self._make_role_dicts()
        RoleService.annotate_effective_needs_approval(roles, self.club.id)
        self.assertTrue(roles[0]['effective_needs_approval'])
        self.assertFalse(roles[1]['effective_needs_approval'])
        # Raw value is preserved.
        self.assertTrue(roles[0]['needs_approval'])

    def test_annotate_policy_on_keeps_needs_approval(self):
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=True,
        ))
        db.session.commit()

        roles = self._make_role_dicts()
        RoleService.annotate_effective_needs_approval(roles, self.club.id)
        self.assertTrue(roles[0]['effective_needs_approval'])
        self.assertFalse(roles[1]['effective_needs_approval'])

    def test_annotate_policy_off_flips_needs_approval(self):
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=False,
        ))
        db.session.commit()

        roles = self._make_role_dicts()
        RoleService.annotate_effective_needs_approval(roles, self.club.id)
        # Toastmaster (needs_approval=True) is now directly bookable.
        self.assertFalse(roles[0]['effective_needs_approval'])
        # Timer (needs_approval=False) stays directly bookable.
        self.assertFalse(roles[1]['effective_needs_approval'])
        # Raw value is preserved — only the effective field flipped.
        self.assertTrue(roles[0]['needs_approval'])
        self.assertFalse(roles[1]['needs_approval'])

    def test_annotate_does_not_mutate_caller_cache(self):
        """The helper should annotate the caller's dicts in-place without
        being confused by shared references (sanity check on input shape)."""
        db.session.add(ClubRule(
            club_id=self.club.id,
            rule_name='direct_booking_approval',
            is_enabled=False,
        ))
        db.session.commit()

        original = self._make_role_dicts()
        roles = [dict(r) for r in original]  # what _get_roles_for_booking does
        RoleService.annotate_effective_needs_approval(roles, self.club.id)
        self.assertIn('effective_needs_approval', roles[0])
        self.assertNotIn('effective_needs_approval', original[0])


if __name__ == '__main__':
    unittest.main()
