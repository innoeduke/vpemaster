"""Assign Topicsmaster owners to Table Topics session logs from a SQL dump.

Reads instance/196957.sql (or any mysqldump-format file) and, for each
Topicsmaster assignment in the dump, resolves the meeting and the Table
Topics session log in the live database, then calls
RoleService.assign_meeting_role so that the OwnerMeetingRoles, Roster,
and Waitlist side effects are all updated.
"""

import argparse
import ast
import os
import re
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


def _parse_date(s):
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def resolve_meeting(club, row):
    meeting_id = str(row.get('meeting_id') or '').strip()
    meeting_number = str(row.get('meeting_number') or '').strip()
    meeting_date = str(row.get('meeting_date') or '').strip()

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
        d = _parse_date(meeting_date)
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


# ---------------------------------------------------------------------------
# SQL dump parsing
# ---------------------------------------------------------------------------

# MySQL type keywords that mark a column definition (vs. KEY/CONSTRAINT).
_COLUMN_TYPE_PATTERN = re.compile(
    r'^\s+`(\w+)`\s+'
    r'(int|smallint|bigint|tinyint|mediumint|'
    r'varchar|char|text|mediumtext|longtext|tinytext|'
    r'date|datetime|time|timestamp|'
    r'float|double|decimal|'
    r'enum|set|json|blob|mediumblob|longblob)',
    re.MULTILINE | re.IGNORECASE,
)


def _read_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def _find_create_block(text, table_name):
    """Return the body of CREATE TABLE `name`, tracking nested parens."""
    needle = f'CREATE TABLE `{table_name}`'
    start = text.find(needle)
    if start == -1:
        return None
    open_paren = text.find('(', start)
    if open_paren == -1:
        return None
    depth = 1
    i = open_paren + 1
    while i < len(text) and depth > 0:
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        i += 1
    if depth != 0:
        return None
    return text[open_paren + 1:i - 1]


def _find_insert_line(text, table_name):
    """Return the single INSERT INTO line for `table_name`, or None."""
    prefix = f'INSERT INTO `{table_name}`'
    for line in text.splitlines():
        if line.startswith(prefix):
            return line
    return None


def _parse_create_columns(create_block):
    """Ordered list of column names from a CREATE TABLE body."""
    return [m.group(1) for m in _COLUMN_TYPE_PATTERN.finditer(create_block)]


def _parse_insert_line(line):
    """Extract row tuples from an `INSERT INTO ... VALUES ...;` line.

    Mirrors the simple ast.literal_eval approach used by
    scripts/load_voting_sql.py: replaces `NULL` with `None` and evaluates
    the whole VALUES payload as Python literals. Standard MySQL backslash
    escapes (`\'`, `\\`, `\n`, ...) are also valid Python escapes, so
    they pass through unchanged.
    """
    match = re.search(r'VALUES\s*(.*);?$', line)
    if not match:
        return []
    payload = match.group(1).strip()
    if payload.endswith(';'):
        payload = payload[:-1]
    payload = payload.replace('NULL', 'None')
    if not payload:
        return []
    try:
        parsed = ast.literal_eval(f'({payload})')
    except (ValueError, SyntaxError) as e:
        print(f'Error parsing VALUES payload: {e}')
        return []
    if isinstance(parsed, tuple) and parsed and not isinstance(parsed[0], tuple):
        parsed = [parsed]
    return list(parsed)


def parse_table(sql_text, table_name):
    """Return all rows of `table_name` from the mysqldump as a list of dicts.

    Returns an empty list if the table is missing from the dump.
    """
    create_block = _find_create_block(sql_text, table_name)
    if create_block is None:
        return []
    columns = _parse_create_columns(create_block)
    if not columns:
        return []

    insert_line = _find_insert_line(sql_text, table_name)
    if insert_line is None:
        return []

    rows = _parse_insert_line(insert_line)
    out = []
    for row in rows:
        if len(row) < len(columns):
            row = list(row) + [None] * (len(columns) - len(row))
        elif len(row) > len(columns):
            row = list(row)[:len(columns)]
        out.append(dict(zip(columns, row)))
    return out


def find_role_id(meeting_roles_rows, name='Topicsmaster'):
    for row in meeting_roles_rows:
        if row.get('name') == name:
            return row.get('id')
    return None


def query_table_topic_owners_from_sql(sql_path, club_id):
    """Yield CSV-shaped rows describing Table Topics owners from `sql_path`.

    Each row has keys: meeting_id, meeting_number, meeting_date,
    meeting_title, table_topics_session_titles, topicsmaster_owner.
    """
    text = _read_text(sql_path)

    meeting_roles = parse_table(text, 'meeting_roles')
    topicsmaster_role_id = find_role_id(meeting_roles, 'Topicsmaster')
    if topicsmaster_role_id is None:
        raise RuntimeError(
            'Could not find a meeting_role named "Topicsmaster" in the SQL dump.'
        )

    meetings = parse_table(text, 'Meetings')
    session_logs = parse_table(text, 'Session_Logs')
    session_types_by_id = {
        st['id']: st for st in parse_table(text, 'Session_Types')
    }
    owner_meeting_roles = parse_table(text, 'owner_meeting_roles')
    contacts_by_id = {c['id']: c for c in parse_table(text, 'Contacts')}

    for m in meetings:
        if m.get('club_id') != club_id:
            continue
        for sl in session_logs:
            if sl.get('meeting_id') != m.get('id'):
                continue
            st = session_types_by_id.get(sl.get('Type_ID'))
            if not st or st.get('role_id') != topicsmaster_role_id:
                continue
            for omr in owner_meeting_roles:
                if omr.get('session_log_id') != sl.get('id'):
                    continue
                if omr.get('role_id') != topicsmaster_role_id:
                    continue
                owner = contacts_by_id.get(omr.get('contact_id'))
                if not owner:
                    continue
                md = m.get('Meeting_Date') or ''
                yield {
                    'meeting_id': m.get('id'),
                    'meeting_number': m.get('Meeting_Number'),
                    'meeting_date': md if isinstance(md, str) else md.isoformat(),
                    'meeting_title': m.get('Meeting_Title') or '',
                    'table_topics_session_titles': st.get('Title') or '',
                    'topicsmaster_owner': owner.get('Name') or '',
                }


def import_table_topic_owners(
    sql_path, club=None, dry_run=True, only_meeting_ids=None
):
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
        print(f'SQL source: {sql_path}')
        print(f'Mode: {"DRY RUN" if dry_run else "WRITE"}')

        if not os.path.exists(sql_path):
            print(f'Error: SQL file not found: {sql_path}')
            return

        only = set(int(x) for x in (only_meeting_ids or []) if str(x).isdigit())

        assigned = 0
        skipped = 0
        errors = 0

        try:
            rows = list(query_table_topic_owners_from_sql(sql_path, club.id))
        except RuntimeError as e:
            print(f'Error: {e}')
            return

        if not rows:
            print('No Table Topics owner rows found in the SQL for this club.')

        for line_no, row in enumerate(rows, start=1):
            meeting_id_raw = str(row.get('meeting_id') or '').strip()
            owner_raw = (row.get('topicsmaster_owner') or '').strip()
            titles_raw = (row.get('table_topics_session_titles') or '').strip()

            if not owner_raw or not titles_raw:
                skipped += 1
                continue

            if only and (not meeting_id_raw or int(meeting_id_raw) not in only):
                continue

            meeting = resolve_meeting(club, row)
            if meeting is None:
                print(
                    f'[row {line_no}] meeting not found for '
                    f'#{row.get("meeting_number")} ({row.get("meeting_title")})'
                )
                errors += 1
                continue

            contact, candidates = resolve_contact(owner_raw)
            if contact is None:
                cands = ', '.join(c.Name for c in candidates[:5]) or '(none)'
                print(
                    f'[row {line_no}] contact "{owner_raw}" not found for meeting '
                    f'#{meeting.Meeting_Number} ({meeting.Meeting_Title}). '
                    f'Closest: {cands}'
                )
                errors += 1
                continue

            for title in [t.strip() for t in titles_raw.split(';') if t.strip()]:
                log = resolve_session_log(meeting, title)
                if log is None:
                    print(
                        f'[row {line_no}] no session log matches "{title}" in meeting '
                        f'#{meeting.Meeting_Number} ({meeting.Meeting_Title})'
                    )
                    errors += 1
                    continue

                if not log.session_type or not log.session_type.role:
                    print(
                        f'[row {line_no}] session log #{log.id} has no role, skipping'
                    )
                    errors += 1
                    continue

                role_name = log.session_type.role.name
                current_owners = ', '.join(o.Name for o in log.owners) or '(none)'

                action = 'would assign' if dry_run else 'assigning'
                print(
                    f'[row {line_no}] meeting #{meeting.Meeting_Number} '
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
        description='Import Topicsmaster owners from a MySQL dump and assign them to Table Topics sessions.'
    )
    parser.add_argument(
        '--sql',
        required=True,
        help='Path to the MySQL dump file (e.g. instance/196957.sql).',
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
        sql_path=args.sql,
        club=club,
        dry_run=not args.write,
        only_meeting_ids=args.only,
    )
