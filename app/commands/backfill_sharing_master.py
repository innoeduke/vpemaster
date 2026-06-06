"""Recompute Meetings.sharing_master_id for every meeting.

Run after:
  - Setting the Featured flag on a Session_Type for the first time
  - Changing which session type is Featured
  - Reassigning owners of a Featured session

Idempotent: safe to run multiple times. The logic lives in
Meeting.update_sharing_master() (filters by Featured, sorts by
Meeting_Seq, takes owners[0]).
"""
import click
from flask.cli import with_appcontext

from app.models.base import db
from app.models.meeting import Meeting


@click.command('meetings:backfill-sharing-master')
@click.option('--dry-run', is_flag=True, help='Print what would change without writing.')
@with_appcontext
def backfill_sharing_master(dry_run):
    """Recompute sharing_master_id for all meetings from Featured Session owners."""
    meetings = Meeting.query.order_by(Meeting.id).all()
    changed = 0
    unchanged = 0
    no_featured = 0

    for m in meetings:
        before = m.sharing_master_id
        m.update_sharing_master()
        after = m.sharing_master_id

        if before == after:
            if after is None:
                no_featured += 1
            else:
                unchanged += 1
        else:
            changed += 1
            click.echo(f"  meeting #{m.Meeting_Number} ({m.Meeting_Date}): {before} -> {after}")

    if dry_run:
        db.session.rollback()
        click.echo(f"[dry-run] {changed} would change, {unchanged} unchanged, {no_featured} have no Featured Session")
        return

    db.session.commit()
    click.echo(f"Done. {changed} updated, {unchanged} unchanged, {no_featured} have no Featured Session.")
