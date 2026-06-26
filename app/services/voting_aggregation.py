"""Vote aggregation helpers for the voting page."""
from sqlalchemy import func
from app.models import Vote
from app import db


def aggregate_votes_for_meeting(meeting_id):
    """Return {(contact_id, award_category): count} for a meeting.

    Replaces three separate GROUP BY queries that previously lived in
    _enrich_role_data_for_voting / role-taker / custom-config blocks of
    _get_roles_for_voting. Admin permission gating is unchanged — callers
    decide whether to call this at all.
    """
    rows = (
        db.session.query(
            Vote.contact_id,
            Vote.award_category,
            func.count(Vote.id),
        )
        .filter(Vote.meeting_id == meeting_id)
        .group_by(Vote.contact_id, Vote.award_category)
        .all()
    )
    return {(cid, cat): n for cid, cat, n in rows if cid and cat}


def aggregate_votes_by_contact_for_meeting(meeting_id, award_category):
    """Return {contact_id: count} restricted to a single award category.

    Used for the role-taker column where the consumer wants a flat
    contact-id-keyed dict instead of the (contact, category) tuple key.
    """
    rows = (
        db.session.query(Vote.contact_id, func.count(Vote.id))
        .filter(
            Vote.meeting_id == meeting_id,
            Vote.award_category == award_category,
        )
        .group_by(Vote.contact_id)
        .all()
    )
    return {cid: n for cid, n in rows if cid}
