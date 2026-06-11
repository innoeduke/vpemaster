import os
import sys
import re
import argparse

# Setup path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.meeting import Meeting
from app.models.contact import Contact
from app.models.voting import MeetingAwardWinner

def parse_meetings_columns(sql_content):
    idx = sql_content.find("CREATE TABLE `Meetings`")
    if idx == -1:
        idx = sql_content.find("CREATE TABLE Meetings")
    if idx == -1:
        return None
        
    start_paren = sql_content.find("(", idx)
    if start_paren == -1:
        return None
        
    paren_depth = 0
    in_string = False
    string_char = None
    escape = False
    end_paren = -1
    
    for i in range(start_paren, len(sql_content)):
        char = sql_content[i]
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if in_string:
            if char == string_char:
                in_string = False
                string_char = None
            continue
        if char in ("'", '"'):
            in_string = True
            string_char = char
            continue
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
            if paren_depth == 0:
                end_paren = i
                break
                
    if end_paren == -1:
        return None
        
    columns_body = sql_content[start_paren+1:end_paren]
    columns = []
    for line in columns_body.split('\n'):
        line = line.strip()
        if not line:
            continue
        if any(line.upper().startswith(keyword) for keyword in ["CONSTRAINT", "PRIMARY KEY", "KEY", "UNIQUE KEY", "UNIQUE"]):
            continue
        col_match = re.match(r"^`?([a-zA-Z0-9_]+)`?", line)
        if col_match:
            columns.append(col_match.group(1))
    return columns

def parse_sql_inserts(sql_content):
    pattern = re.compile(r"INSERT\s+INTO\s+`Meetings`\s+VALUES\s*", re.IGNORECASE)
    meetings = []
    
    for match in pattern.finditer(sql_content):
        start_idx = match.end()
        idx = start_idx
        in_string = False
        string_char = None
        escape = False
        in_tuple = False
        current_val = []
        current_tuple = []
        
        while idx < len(sql_content):
            char = sql_content[idx]
            
            if escape:
                current_val.append(char)
                escape = False
                idx += 1
                continue
                
            if char == '\\':
                escape = True
                current_val.append(char)
                idx += 1
                continue
                
            if in_string:
                if char == string_char:
                    in_string = False
                    string_char = None
                current_val.append(char)
            else:
                if char in ("'", '"'):
                    in_string = True
                    string_char = char
                    current_val.append(char)
                elif char == '(':
                    if not in_tuple:
                        in_tuple = True
                        current_tuple = []
                        current_val = []
                    else:
                        current_val.append(char)
                elif char == ')':
                    if in_tuple:
                        val_str = "".join(current_val).strip()
                        current_tuple.append(val_str)
                        meetings.append(current_tuple)
                        in_tuple = False
                        current_tuple = []
                        current_val = []
                elif char == ',':
                    if in_tuple:
                        val_str = "".join(current_val).strip()
                        current_tuple.append(val_str)
                        current_val = []
                elif char == ';':
                    break
                else:
                    if in_tuple:
                        current_val.append(char)
            idx += 1
            
    return meetings

def clean_val(val):
    if val.upper() == 'NULL':
        return None
    if val.startswith("'") and val.endswith("'"):
        s = val[1:-1]
        s = s.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n').replace('\\r', '\r')
        return s
    if val.startswith('"') and val.endswith('"'):
        s = val[1:-1]
        s = s.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n').replace('\\r', '\r')
        return s
    try:
        if '.' in val:
            return float(val)
        return int(val)
    except ValueError:
        return val

def find_latest_backup():
    # Search for backup_db_full_*.sql under instance/backup/db/
    backup_dir = os.path.join('instance', 'backup', 'db')
    if os.path.exists(backup_dir):
        files = [f for f in os.listdir(backup_dir) if f.startswith('backup_db_full_') and f.endswith('.sql')]
        if files:
            files.sort(reverse=True)
            return os.path.join(backup_dir, files[0])
            
    # Fallback to instance/backup_prior_upgrade.sql
    fallback = os.path.join('instance', 'backup_prior_upgrade.sql')
    if os.path.exists(fallback):
        return fallback
        
    return None

def main():
    parser = argparse.ArgumentParser(description="Migrate historical award winners from a backup SQL file.")
    parser.add_argument("backup_file", nargs="?", help="Path to the backup SQL file (defaults to the latest found).")
    parser.add_argument("--dry-run", action="store_true", help="Preview the migration without committing changes to the database.")
    args = parser.parse_args()
    
    backup_file = args.backup_file
    if not backup_file:
        backup_file = find_latest_backup()
        if not backup_file:
            print("Error: No backup SQL file specified and none could be found automatically.")
            sys.exit(1)
            
    print(f"Using backup file: {backup_file}")
    if args.dry_run:
        print("NOTE: Running in DRY-RUN mode. No changes will be written to the database.")
        
    try:
        with open(backup_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading backup file: {e}")
        sys.exit(1)
        
    columns = parse_meetings_columns(content)
    if not columns:
        print("Error: Could not find Meetings table columns in the backup file.")
        sys.exit(1)
        
    tuples = parse_sql_inserts(content)
    print(f"Parsed {len(tuples)} meetings from backup INSERT statements.")
    
    award_cols = {
        'best_table_topic_id': 'table-topic',
        'best_evaluator_id': 'evaluator',
        'best_speaker_id': 'speaker',
        'best_role_taker_id': 'role-taker',
        'best_debater_id': 'debater'
    }
    
    active_awards = {col: cat for col, cat in award_cols.items() if col in columns}
    print(f"Award columns mapped from backup schema: {list(active_awards.keys())}")
    
    app = create_app()
    with app.app_context():
        # Pre-query existing meetings and contacts to validate foreign keys
        valid_meetings = {m.id for m in Meeting.query.all()}
        valid_contacts = {c.id for c in Contact.query.all()}
        
        # Pre-query existing award winners to avoid duplicates
        existing_winners = set()
        winners_in_db = MeetingAwardWinner.query.all()
        for w in winners_in_db:
            existing_winners.add((w.meeting_id, w.award_category, w.contact_id))
            
        print(f"Active DB has {len(valid_meetings)} meetings, {len(valid_contacts)} contacts, and {len(existing_winners)} award winner entries.")
        
        added_count = 0
        skipped_fk_count = 0
        skipped_dup_count = 0
        
        for row in tuples:
            if len(row) != len(columns):
                continue
                
            meeting_id = clean_val(row[columns.index('id')])
            if meeting_id not in valid_meetings:
                # Skip if meeting doesn't exist in current active DB
                # Collect how many winners we'd skip
                for col in active_awards:
                    if clean_val(row[columns.index(col)]) is not None:
                        skipped_fk_count += 1
                continue
                
            for col, cat in active_awards.items():
                contact_id = clean_val(row[columns.index(col)])
                if contact_id is None:
                    continue
                    
                if contact_id not in valid_contacts:
                    skipped_fk_count += 1
                    print(f"Warning: contact_id {contact_id} for meeting {meeting_id} ({cat}) not found in current database. Skipping.")
                    continue
                    
                if (meeting_id, cat, contact_id) in existing_winners:
                    skipped_dup_count += 1
                    continue
                    
                # Safe to insert
                if not args.dry_run:
                    winner = MeetingAwardWinner(
                        meeting_id=meeting_id,
                        award_category=cat,
                        contact_id=contact_id
                    )
                    db.session.add(winner)
                    # Add to local set to prevent duplicate inserts in the same run if any
                    existing_winners.add((meeting_id, cat, contact_id))
                
                added_count += 1
                print(f"Queued: Meeting {meeting_id} -> Category '{cat}' -> Contact {contact_id}")
                
        if not args.dry_run and added_count > 0:
            db.session.commit()
            print(f"\nSuccessfully committed {added_count} new award winners to the database.")
        else:
            print(f"\nDry-run complete. Would have added {added_count} new award winners.")
            
        print(f"Summary: Added={added_count}, Skipped (FK missing)={skipped_fk_count}, Skipped (Already exists)={skipped_dup_count}")

if __name__ == '__main__':
    main()
