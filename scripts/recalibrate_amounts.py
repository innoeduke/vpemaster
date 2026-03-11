"""
Recalibrate roster entry amounts for a specific meeting.

For each roster entry:
1. Look up the assigned ticket by ticket_id
2. If the ticket's type doesn't match the entry's contact_type,
   find the correct ticket variant (same name, matching type)
3. Update ticket_id and amount accordingly

Usage:
    python scripts/recalibrate_amounts.py <meeting_id> [--dry-run]
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app, db
from app.models.roster import Roster
from app.models.ticket import Ticket
from app.models.meeting import Meeting


def recalibrate_meeting(meeting_id, dry_run=False):
    meeting = db.session.get(Meeting, meeting_id)
    if not meeting:
        print(f"❌ Meeting ID {meeting_id} not found.")
        return

    print(f"Meeting #{meeting.Meeting_Number} (ID: {meeting_id}) - {meeting.Meeting_Date}")
    print("-" * 70)

    entries = Roster.query.filter_by(meeting_id=meeting_id).all()
    if not entries:
        print("No roster entries found.")
        return

    # Build a lookup: (name, type) -> Ticket
    club_id = meeting.club_id
    all_tickets = Ticket.get_all_for_club(club_id)
    ticket_lookup = {(t.name, t.type): t for t in all_tickets}

    updated = 0
    for entry in entries:
        contact_name = entry.contact.Name if entry.contact else "Unknown"
        contact_type = entry.contact_type or "Guest"
        old_ticket = entry.ticket
        old_amount = entry.amount or 0.0

        if not old_ticket:
            print(f"  ⚠  #{entry.order_number} {contact_name}: No ticket assigned, skipping.")
            continue

        # Find the correct ticket variant matching (ticket_name, contact_type)
        correct_ticket = ticket_lookup.get((old_ticket.name, contact_type))

        # Fallback: if no exact match, try the current ticket itself
        if not correct_ticket:
            correct_ticket = old_ticket

        new_amount = correct_ticket.price or 0.0
        ticket_changed = correct_ticket.id != old_ticket.id
        amount_changed = abs(new_amount - old_amount) > 0.001

        if not ticket_changed and not amount_changed:
            print(f"  ✓  #{entry.order_number} {contact_name}: {old_ticket.name} ({contact_type}) ¥{old_amount:.2f} — OK")
            continue

        # Report changes
        changes = []
        if ticket_changed:
            changes.append(f"ticket: {old_ticket.name}[{old_ticket.type}] → {correct_ticket.name}[{correct_ticket.type}]")
        if amount_changed:
            changes.append(f"amount: ¥{old_amount:.2f} → ¥{new_amount:.2f}")

        action = "WOULD UPDATE" if dry_run else "UPDATED"
        print(f"  ✏  #{entry.order_number} {contact_name}: {action} — {', '.join(changes)}")

        if not dry_run:
            entry.ticket_id = correct_ticket.id
            entry.ticket = correct_ticket
            entry.amount = new_amount
            updated += 1

    if not dry_run and updated > 0:
        db.session.commit()

    print("-" * 70)
    mode = "(DRY RUN)" if dry_run else ""
    print(f"Done. {updated} entries updated {mode}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/recalibrate_amounts.py <meeting_id> [--dry-run]")
        sys.exit(1)

    meeting_id = int(sys.argv[1])
    dry_run = "--dry-run" in sys.argv

    app = create_app()
    with app.app_context():
        recalibrate_meeting(meeting_id, dry_run=dry_run)
