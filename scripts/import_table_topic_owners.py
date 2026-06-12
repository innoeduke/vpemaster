"""Assign Topicsmaster owners to Table Topics session logs from a CSV.

Reads instance/table_topics_owners.csv and, for each row, resolves the
meeting and the Table Topics session log, then uses
RoleService.assign_meeting_role so that the OwnerMeetingRoles, Roster,
and Waitlist side effects are all updated.
"""

import argparse
import csv
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.club_context import get_current_club_id
from app.models import Contact, Meeting, SessionLog, SessionType
from app.services.role_service import RoleService


def resolve_club(club_no=None, club_id=None):
    from app.models.club import Club

    if club_id is not None:
        return db.session.get(Club, club_id)
    if club_no is not None:
        club = Club.query.filter_by(club_no=str(club_no)).first()
        if club:
            return club
        if str(club_no).isdigit():
            return db.session.get(Club, int(club_no))
    return None


def resolve_meeting(club, row):
    meeting_id = (row.get('meeting_id') or '').strip()
    meeting_number = (row.get('meeting_number') or '').strip()
    meeting_date = (row.get('meeting_date') or '').strip()

    if meeting_id:
        m = db.session.get(Meeting, int(meeting_id))
        if m and m.club_id == club.id:
            return m

    if meeting_number:
        m = Meeting.query.filter_by(
            club_id=club.id, Meeting_Number=int(meeting_number)
        ).first()
        if m:
            return m

    if meeting_date:
        try:
            d = datetime.strptime(meeting_date, '%Y/%m/%d').date()
        except ValueError:
            d = None
        if d:
            m = Meeting.query.filter_by(club_id=club.id, Meeting_Date=d).first()
            if m:
                return m

    return None


def resolve_contact(name):
    if not name:
        return None, []
    name = name.strip().lstrip('!').strip()
    if not name:
        return None, []

    contact = Contact.query.filter_by(Name=name).first()
    if contact:
        return contact, []

    parts = name.split()
    if len(parts) >= 2:
        contact = Contact.query.filter_by(
            first_name=parts[0], last_name=parts[-1]
        ).first()
        if contact:
            return contact, []

    candidates = Contact.query.filter(Contact.Name.ilike(f'%{name}%')).all()
    return None, candidates


def resolve_session_log(meeting, title):
    """Find the session log for `title` in the meeting.

    Matching order:
      1. Exact SessionType.Title match against meeting session logs.
      2. Case-insensitive exact match on Title.
      3. Fuzzy match using the difflib ratio for any session type whose
         title contains 'table' or 'topic' or 'topicsmaster'.
    Returns the SessionLog (with session_type loaded) or None.
    """
    from difflib import SequenceMatcher

    if not title:
        return None

    title_norm = title.strip().lower()
    logs = (
        SessionLog.query
        .options(db.joinedload(SessionLog.session_type).joinedload(SessionType.role))
        .filter(SessionLog.meeting_id == meeting.id)
        .all()
    )

    for log in logs:
        if log.session_type and log.session_type.Title == title:
            return log

    for log in logs:
        if log.session_type and log.session_type.Title.lower() == title_norm:
            return log

    candidates = []
    for log in logs:
        if not log.session_type:
            continue
        st_title = log.session_type.Title.lower()
        if 'table' in st_title or 'topic' in st_title or 'topicsmaster' in st_title:
            ratio = SequenceMatcher(None, st_title, title_norm).ratio()
            candidates.append((ratio, log))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_ratio, best_log = candidates[0]
        if best_ratio >= 0.5:
            return best_log

    return None


def import_table_topic_owners(csv_path, club=None, dry_run=True, only_meeting_ids=None):
    app = create_app()
    with app.app_context():
        if club is None:
            club_id = get_current_club_id()
            from app.models.club import Club
            club = db.session.get(Club, club_id) if club_id else Club.query.first()

        if club is None:
            print('Error: No club resolved.')
            return

        print(f'Targeting club: {club.club_name} (ID={club.id})')
        print(f'Mode: {"DRY RUN" if dry_run else "WRITE"}')

        if not os.path.exists(csv_path):
            print(f'Error: CSV not found: {csv_path}')
            return

        only = set(int(x) for x in (only_meeting_ids or []) if str(x).isdigit())

        assigned = 0
        skipped = 0
        errors = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for line_no, row in enumerate(reader, start=2):
                meeting_id_raw = (row.get('meeting_id') or '').strip()
                owner_raw = (row.get('topicsmaster_owner') or '').strip()
                titles_raw = (row.get('table_topics_session_titles') or '').strip()

                if not owner_raw or not titles_raw:
                    skipped += 1
                    continue

                if only and (not meeting_id_raw or int(meeting_id_raw) not in only):
                    continue

                meeting = resolve_meeting(club, row)
                if meeting is None:
                    print(f'[line {line_no}] meeting not found for row: {row.get("meeting_title")}')
                    errors += 1
                    continue

                contact, candidates = resolve_contact(owner_raw)
                if contact is None:
                    cands = ', '.join(c.Name for c in candidates[:5]) or '(none)'
                    print(
                        f'[line {line_no}] contact "{owner_raw}" not found for meeting '
                        f'#{meeting.Meeting_Number} ({meeting.Meeting_Title}). '
                        f'Closest: {cands}'
                    )
                    errors += 1
                    continue

                for title in [t.strip() for t in titles_raw.split(';') if t.strip()]:
                    log = resolve_session_log(meeting, title)
                    if log is None:
                        print(
                            f'[line {line_no}] no session log matches "{title}" in meeting '
                            f'#{meeting.Meeting_Number} ({meeting.Meeting_Title})'
                        )
                        errors += 1
                        continue

                    if not log.session_type or not log.session_type.role:
                        print(
                            f'[line {line_no}] session log #{log.id} has no role, skipping'
                        )
                        errors += 1
                        continue

                    role_name = log.session_type.role.name
                    current_owners = ', '.join(o.Name for o in log.owners) or '(none)'

                    action = 'would assign' if dry_run else 'assigning'
                    print(
                        f'[line {line_no}] meeting #{meeting.Meeting_Number} '
                        f'"{meeting.Meeting_Title}" — {action} {contact.Name} as '
                        f'{role_name} on "{log.session_type.Title}" (was: {current_owners})'
                    )

                    if not dry_run:
                        RoleService.assign_meeting_role(
                            log, [contact.id], is_admin=True
                        )
                    assigned += 1

        if not dry_run:
            db.session.commit()
            print('Committed changes.')
        else:
            db.session.rollback()
            print('Rolled back (dry run).')

        print(f'\nSummary: assigned={assigned} skipped={skipped} errors={errors}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Import Topicsmaster owners from CSV and assign them to Table Topics sessions.'
    )
    parser.add_argument(
        '--file',
        default='instance/table_topics_owners.csv',
        help='Path to the input CSV',
    )
    parser.add_argument('--club-no', help='Club number to target')
    parser.add_argument(
        '--write',
        action='store_true',
        help='Persist changes. Default is a dry run that rolls back.',
    )
    parser.add_argument(
        '--only',
        nargs='+',
        help='Restrict to specific meeting_id values (space separated).',
    )
    args = parser.parse_args()

    club = None
    if args.club_no:
        app = create_app()
        with app.app_context():
            club = resolve_club(club_no=args.club_no)

    import_table_topic_owners(
        csv_path=args.file,
        club=club,
        dry_run=not args.write,
        only_meeting_ids=args.only,
    )
