
import sys
import os
import re
import openpyxl
from datetime import datetime, time
from difflib import get_close_matches, SequenceMatcher

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.meeting import Meeting
from app.models.contact import Contact
from app.models.session import SessionLog, SessionType, OwnerMeetingRoles
from app.models.club import Club
from app.models.project import Project, Pathway, PathwayProject
from app.models.achievement import Achievement
from collections import defaultdict

def get_historical_credential(contact_id, meeting_date, path_abbr_map):
    """
    Determine the highest credential held by the contact strictly BEFORE or ON the meeting date.
    """
    if not meeting_date or not contact_id:
        return None
        
    # Fetch relevant achievements
    achievements = Achievement.query.filter(
        Achievement.contact_id == contact_id,
        Achievement.issue_date <= meeting_date,
        Achievement.achievement_type.in_(['level-completion', 'program-completion'])
    ).all()
    
    if not achievements:
        return None
        
    valid_creds = []
    for a in achievements:
        # Handle DTM
        if a.achievement_type == 'program-completion' and 'Distinguished Toastmaster' in a.path_name:
             # Match exact or roughly? Usually "Distinguished Toastmasters"
             # Assuming 'Distinguished Toastmasters' from fix script check
             valid_creds.append({'level': 99, 'abbr': 'DTM', 'is_dtm': True, 'date': a.issue_date})
             continue

        abbr = path_abbr_map.get(a.path_name)
        if abbr and a.level:
            valid_creds.append({'level': a.level, 'abbr': abbr, 'is_dtm': False, 'date': a.issue_date})
            
    if not valid_creds:
        return None
        
    # Sort: Highest Level > Latest Date
    valid_creds.sort(key=lambda x: (x['level'], x['date']), reverse=True)
    top = valid_creds[0]
    
    if top.get('is_dtm'):
        return "DTM"
    return f"{top['abbr']}{top['level']}"


def import_sessions(file_path, target_club_no=None):
    app = create_app()
    with app.app_context():
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return

        print(f"Loading workbook: {file_path}")
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active

        # Mapping of headers to indices
        headers = [cell.value for cell in sheet[1]]
        idx = {name: i for i, name in enumerate(headers)}
        
        required_cols = ['Meeting_Number', 'Owner Contact ID', 'Session']
        for col in required_cols:
            if col not in idx:
                print(f"Error: Missing required column {col}")
                return

        # Resolve Club
        club = None
        if target_club_no:
            club = Club.query.filter_by(club_no=str(target_club_no)).first()
            if not club and str(target_club_no).isdigit():
                club = Club.query.get(int(target_club_no))
        
        if not club:
            club = Club.query.first()
            if not club:
                 print("Error: No club found.")
                 return
        
        print(f"Targeting Club: {club.club_name} (ID: {club.id})")

        # Cache Session Types for Fuzzy Matching
        all_types = SessionType.get_all_for_club(club.id)
        type_map = {t.Title.lower(): t for t in all_types}
        type_titles = list(type_map.keys())

        # Cache Pathway Abbreviations
        all_pathways = Pathway.query.all()
        path_abbr_map = {p.name: p.abbr for p in all_pathways if p.name and p.abbr}


        count = 0
        skipped = 0
        
        # 1. Group rows by Meeting
        meeting_groups = defaultdict(list)
        
        # Read all relevant rows first
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            meeting_no = row[idx['Meeting_Number']]
            
            # User Request: Only import meetings before 934
            try:
                if meeting_no and int(meeting_no) >= 934:
                    continue
            except (ValueError, TypeError):
                pass
            
            if meeting_no:
                meeting_groups[meeting_no].append((row_idx, row))
        
        print(f"Found {len(meeting_groups)} meetings to process.")
        
        # 2. Process each meeting
        sorted_meeting_numbers = sorted(meeting_groups.keys())
        
        for meeting_no in sorted_meeting_numbers:
            rows = meeting_groups[meeting_no]
            parsed_sessions = []
            
            # 2a. Parse all rows for this meeting
            meeting_obj = Meeting.query.filter_by(Meeting_Number=meeting_no, club_id=club.id).first()
            if not meeting_obj:
                print(f"Meeting {meeting_no} not found in club {club.id}. Skipping {len(rows)} rows.")
                skipped += len(rows)
                continue
                
            for row_idx, row in rows:
                session_raw = row[idx['Session']]
                owner_name_raw = row[idx['Owner Contact ID']]
                
                if not session_raw:
                    continue

                # --- Parsing Logic ---
                # Find Owner
                contact = None
                if owner_name_raw:
                    owner_name = str(owner_name_raw).strip()
                    contact = Contact.query.filter_by(Name=owner_name).first()
                    if not contact:
                        parts = owner_name.split()
                        if len(parts) >= 2:
                            contact = Contact.query.filter_by(first_name=parts[0], last_name=parts[-1]).first()
                    if not contact:
                         print(f"[Row {row_idx}] Contact '{owner_name}' not found. Skipping.")
                         skipped += 1
                         continue
                else:
                    print(f"[Row {row_idx}] No owner name provided. Skipping.")
                    skipped += 1
                    continue

                # Parse Session
                # Clean up quotes (including smart quotes) from start/end
                session_text = str(session_raw).strip().strip('"').strip('“').strip('”')
                
                start_time = row[idx['Start_Time']] if 'Start_Time' in idx else None
                duration_raw = row[idx['Duration']] if 'Duration' in idx else None
                
                # Time/Duration parsing
                parsed_start_time = None
                if start_time:
                    if isinstance(start_time, (datetime, time)):
                        parsed_start_time = start_time if isinstance(start_time, time) else start_time.time()
                    elif isinstance(start_time, str):
                        try:
                            parsed_start_time = datetime.strptime(start_time, "%H:%M").time()
                        except ValueError:
                             try:
                                 parsed_start_time = datetime.strptime(start_time, "%H:%M:%S").time()
                             except ValueError:
                                 pass
                
                dur_min, dur_max = 0, 0
                if duration_raw:
                    d_str = str(duration_raw).strip()
                    if '-' in d_str:
                        try:
                            parts = d_str.split('-')
                            dur_min = int(parts[0].strip())
                            dur_max = int(parts[1].strip())
                        except ValueError:
                            pass
                    elif d_str.isdigit():
                         dur_max = int(d_str)

                project_code = None
                session_title = session_text
                target_type = None
                project_id = None
                
                # Regex for Code
                match = re.match(r"^([A-Z]{1,5}\d+(?:\.[\d]+)+|[A-Z]{1,5}\d+)(.*)", session_text)
                if match:
                    possible_code = match.group(1).strip()
                    rest = match.group(2).strip()
                    code_match = re.match(r"([A-Z]+)(\d.*)", possible_code)
                    if code_match:
                        abbr = code_match.group(1)
                        code_suffix = code_match.group(2)
                        found_pp = db.session.query(PathwayProject).join(Pathway).filter(
                            Pathway.abbr == abbr, PathwayProject.code == code_suffix
                        ).first()
                        if found_pp:
                            project_code = possible_code
                            project_id = found_pp.project_id
                            found_project = Project.query.get(project_id)
                            session_title = rest if rest else (found_project.Project_Name if found_project else "Speech")
                            target_type = type_map.get('prepared speech') or type_map.get('speech')

                # Evaluation Cleanup
                eval_match = re.search(r"^(?:Evaluator for|IE to|\s)+\s*(?:|IE to\s+)?(.*)", session_title, re.IGNORECASE)
                if "IE to" in session_text or "Evaluator for" in session_text:
                    target_type = type_map.get('evaluation') or type_map.get('evaluator') or type_map.get('individual evaluation')
                    if not target_type:
                         for t in type_titles:
                             if 'evaluation' in t or 'evaluator' in t:
                                 target_type = type_map[t]
                                 break
                    if eval_match:
                         session_title = eval_match.group(1).strip()

                # Fuzzy Match
                if not target_type:
                    title_lower = session_title.lower()
                    if title_lower in type_map:
                        target_type = type_map[title_lower]
                    else:
                        matches = get_close_matches(title_lower, type_titles, n=1, cutoff=0.6)
                        if matches:
                            target_type = type_map[matches[0]]
                        elif 'topic' in title_lower:
                            target_type = type_map.get('table topics master') or type_map.get('table topic master')
                        elif 'toastmaster' in title_lower:
                             target_type = type_map.get('toastmaster of the evening') or type_map.get('toastmaster')

                if not target_type and project_id:
                    target_type = type_map.get('prepared speech')

                if not target_type:
                    target_type = type_map.get('speaker') or type_map.get('prepared speech')
                    if not target_type:
                        target_type = all_types[0] if all_types else None
                
                if not target_type:
                    print(f"[Row {row_idx}] Fatal: No session types available.")
                    continue

                parsed_sessions.append({
                    'row_idx': row_idx,
                    'contact': contact,
                    'session_title': session_title,
                    'target_type': target_type,
                    'project_id': project_id,
                    'project_code': project_code,
                    'start_time': parsed_start_time,
                    'dur_min': dur_min,
                    'dur_max': dur_max,
                    'meeting': meeting_obj
                })

            # 2b. Filter & Sort
            # Filter out Section Sessions (Headers)
            # Criteria: Is_Section=True OR specific titles
            filtered_sessions = []
            for s in parsed_sessions:
                tt = s['target_type']
                title = s['session_title'].lower()
                
                is_section = False
                if getattr(tt, 'Is_Section', False):
                    is_section = True
                elif title in ['prepared speeches', 'evaluation reports', 'table topics session']:
                     is_section = True
                
                if not is_section:
                    filtered_sessions.append(s)
            
            # Sort remaining by Start Time
            # Handle None times by putting them at the end? Or start? 
            # Usually strict sorting requires comparable types. 
            # Use 00:00:00 for None to be safe, or 23:59:59.
            filtered_sessions.sort(key=lambda x: x['start_time'] if x['start_time'] else time(0,0))
            
            final_list = filtered_sessions

            # 2c. Write to DB
            existing_meeting_logs = SessionLog.query.filter_by(Meeting_Number=meeting_no).all()
            
            for seq, s_data in enumerate(final_list, start=1):
                contact = s_data['contact']
                session_title = s_data['session_title']
                row_idx = s_data['row_idx']
                
                # Duplicate Check with Pre-fetched logs
                is_dup = False
                found_log = None
                
                for log in existing_meeting_logs:
                    owners = log.owners
                    owner_ids = [o.id for o in owners]
                    if contact.id not in owner_ids: continue
                    
                    t1, t2 = log.Session_Title.lower(), session_title.lower()
                    
                    is_t2_eval = 'evaluator' in t2 or 'ie to' in t2 or 'evaluation' in t2
                    is_t1_eval = 'evaluator' in t1 or 'ie to' in t1 or 'evaluation' in t1
                    
                    match = False
                    if log.Session_Title == session_title: match = True
                    elif SequenceMatcher(None, t1, t2).ratio() > 0.8: match = True
                    elif (is_t2_eval or is_t1_eval):
                         s1, s2 = set(t1.split()), set(t2.split())
                         stopwords = {'evaluator', 'evaluation', 'ie', 'to', 'for', 'speech', 'project', 'report'}
                         if [w for w in s1.intersection(s2) if w not in stopwords]: match = True
                    
                    if match:
                        is_dup = True
                        found_log = log
                        break
                
                if is_dup and found_log:
                     # Update
                     updated = False
                     if found_log.Meeting_Seq != seq:
                         print(f"[Row {row_idx}] Updating sequence for duplicate '{session_title}': {found_log.Meeting_Seq} -> {seq}")
                         found_log.Meeting_Seq = seq
                         updated = True
                     if s_data['start_time'] and found_log.Start_Time != s_data['start_time']:
                         found_log.Start_Time = s_data['start_time']
                         updated = True
                     if s_data['dur_max'] > 0:
                         if found_log.Duration_Max != s_data['dur_max']:
                             found_log.Duration_Max = s_data['dur_max']
                             updated = True
                         if found_log.Duration_Min != s_data['dur_min']:
                             found_log.Duration_Min = s_data['dur_min']
                             updated = True
                     
                     if updated:
                         db.session.add(found_log)
                     skipped += 1
                     continue

                session_log = SessionLog(
                    Meeting_Number=meeting_no,
                    Meeting_Seq=seq,
                    Session_Title=session_title,
                    Type_ID=s_data['target_type'].id,
                    Project_ID=s_data['project_id'],
                    project_code=s_data['project_code'],
                    Status='Completed',
                    Start_Time=s_data['start_time'],
                    Duration_Min=s_data['dur_min'],
                    Duration_Max=s_data['dur_max']
                )
                
                db.session.add(session_log)
                db.session.flush()
                
                role_id = s_data['target_type'].role_id
                if role_id:
                    # Determine historical credential
                    hist_cred = get_historical_credential(contact.id, meeting_obj.Meeting_Date, path_abbr_map)
                    
                    omr = OwnerMeetingRoles(
                        meeting_id=meeting_obj.id,
                        role_id=role_id,
                        contact_id=contact.id,
                        session_log_id=session_log.id,
                        credential=hist_cred  # Use historical instead of current contact.credentials
                    )
                    db.session.add(omr)
                
                count += 1
            
            db.session.commit()
        print(f"Done. Imported {count} sessions. Skipped {skipped}.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import session logs from Excel.')
    parser.add_argument('--file', default='instance/sources/sessions.xlsx', help='Path to Excel file')
    parser.add_argument('--club-no', help='Club Number to import into')
    args = parser.parse_args()
    
    import_sessions(args.file, args.club_no)
