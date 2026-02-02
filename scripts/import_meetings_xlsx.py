import sys
import os
import openpyxl
from datetime import datetime, time, date

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.meeting import Meeting
from app.models.contact import Contact
from app.models.contact_club import ContactClub
from app.models.media import Media
from app.models.club import Club
from app.models.excomm import ExComm

def import_meetings(file_path, target_club_no=None):
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
        
        required_cols = ['Meeting_Number', 'Meeting_Date', 'Meeting_Title']
        for col in required_cols:
            if col not in idx:
                print(f"Error: Missing required column {col}")
                return

        meeting_count = 0
        new_contacts_count = 0
        media_count = 0

        # Start from row 2
        for row in sheet.iter_rows(min_row=2, values_only=True):
            meeting_no = row[idx['Meeting_Number']]
            if meeting_no is None:
                continue

            # 1. Resolve Club
            club = None
            
            # Priority 1: Command line argument
            if target_club_no:
                club = Club.query.filter_by(club_no=str(target_club_no)).first()
                if not club and str(target_club_no).isdigit():
                    club = Club.query.get(int(target_club_no))

            # Priority 2: Excel club_id column
            if not club:
                excel_club_val = str(row[idx['club_id']]) if 'club_id' in idx and row[idx['club_id']] else None
                if excel_club_val:
                    # Try matching club_no
                    club = Club.query.filter_by(club_no=excel_club_val).first()
                    # Try matching id if numeric
                    if not club and excel_club_val.isdigit():
                        club = Club.query.get(int(excel_club_val))

            if not club:
                # Fallback: Get the first club if only one exists, or log error
                club = Club.query.first()
                if not club:
                    print(f"Error: No club found in database. Skipping row {meeting_no}")
                    continue

            # 2. Handle Media
            media_url = row[idx['Media_URL']] if 'Media_URL' in idx else None
            media_id = None
            if media_url:
                media = Media.query.filter_by(url=media_url).first()
                if not media:
                    media = Media(url=media_url)
                    db.session.add(media)
                    db.session.flush()
                    media_count += 1
                media_id = media.id

            # 3. Handle Contacts (H-L)
            contact_cols = [
                ('Table Topic Winner', 'best_table_topic_id'),
                ('Best Evaluator', 'best_evaluator_id'),
                ('Best Speaker', 'best_speaker_id'),
                ('Best Role Taker', 'best_role_taker_id'),
                ('Keynote Speaker', 'manager_id')
            ]
            
            contact_ids = {}
            for col_name, field_name in contact_cols:
                contact_names_val = row[idx[col_name]] if col_name in idx else None
                if not contact_names_val:
                    contact_ids[field_name] = None
                    continue

                # Split by comma for multiple contacts
                names = [n.strip() for n in str(contact_names_val).split(',') if n.strip()]
                first_contact_id = None
                
                for contact_name in names:
                    contact = Contact.query.filter_by(Name=contact_name).first()
                    if not contact:
                        parts = contact_name.split(' ', 1)
                        first_name = "!" + parts[0]
                        last_name = parts[1] if len(parts) > 1 else None
                        
                        contact = Contact(
                            Name=contact_name,
                            first_name=first_name,
                            last_name=last_name,
                            Type='Guest',
                            Date_Created=date.today()
                        )
                        db.session.add(contact)
                        db.session.flush()
                        new_contacts_count += 1
                        print(f"Created new contact: {contact.Name} (first_name: {contact.first_name}, date: {contact.Date_Created})")
                    
                    cc = ContactClub.query.filter_by(contact_id=contact.id, club_id=club.id).first()
                    if not cc:
                        cc = ContactClub(contact_id=contact.id, club_id=club.id)
                        db.session.add(cc)
                    
                    if first_contact_id is None:
                        first_contact_id = contact.id
                
                contact_ids[field_name] = first_contact_id

            # 4. Handle Meeting Override
            meeting = Meeting.query.filter_by(Meeting_Number=meeting_no).first()
            if not meeting:
                meeting = Meeting(Meeting_Number=meeting_no, club_id=club.id)
                db.session.add(meeting)
            else:
                meeting.club_id = club.id # Ensure it's in the right club

            # Update fields
            meeting.Meeting_Date = row[idx['Meeting_Date']]
            meeting.Meeting_Title = row[idx['Meeting_Title']]
            meeting.Subtitle = row[idx['Subtitle']] if 'Subtitle' in idx else None
            
            start_time_val = row[idx['Start_Time']] if 'Start_Time' in idx else None
            if isinstance(start_time_val, time):
                meeting.Start_Time = start_time_val
            elif isinstance(start_time_val, datetime):
                meeting.Start_Time = start_time_val.time()
            
            meeting.Meeting_Template = row[idx['Meeting_Template']] if 'Meeting_Template' in idx else None
            meeting.WOD = row[idx['WOD']] if 'WOD' in idx else None
            meeting.status = row[idx['status']] if 'status' in idx and row[idx['status']] else 'unpublished'
            meeting.ge_mode = row[idx['ge_mode']] if 'ge_mode' in idx and row[idx['ge_mode']] is not None else 0
            
            meeting.media_id = media_id
            meeting.best_table_topic_id = contact_ids['best_table_topic_id']
            meeting.best_evaluator_id = contact_ids['best_evaluator_id']
            meeting.best_speaker_id = contact_ids['best_speaker_id']
            meeting.best_role_taker_id = contact_ids['best_role_taker_id']
            meeting.manager_id = contact_ids['manager_id']

            # Resolve Excomm if present
            excomm_val = row[idx['Excomm']] if 'Excomm' in idx else None
            if excomm_val:
                excomm_val_str = str(excomm_val).strip()
                excomm = ExComm.query.filter(
                    (ExComm.excomm_name == excomm_val_str) | 
                    (ExComm.excomm_term == excomm_val_str) |
                    (ExComm.id == (int(excomm_val) if str(excomm_val).isdigit() else -1))
                ).filter_by(club_id=club.id).first()
                
                if not excomm and ' ' in excomm_val_str:
                    parts = excomm_val_str.split(' ', 1)
                    term = parts[0]
                    name = parts[1].strip('" ')
                    excomm = ExComm.query.filter_by(excomm_term=term, excomm_name=name, club_id=club.id).first()
                    if not excomm:
                        excomm = ExComm.query.filter_by(excomm_term=term, club_id=club.id).first()
                
                if excomm:
                    meeting.excomm_id = excomm.id

            meeting_count += 1
            if meeting_count % 10 == 0:
                print(f"Processed {meeting_count} meetings...")

        db.session.commit()
        print(f"\nImport Completed:")
        print(f"- Meetings processed: {meeting_count}")
        print(f"- New contacts created: {new_contacts_count}")
        print(f"- New media entries: {media_count}")
        print(f"- Targeted Club: {club.club_name} (ID: {club.id})")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import meetings from Excel.')
    parser.add_argument('--file', default='instance/sources/meetings.xlsx', help='Path to Excel file')
    parser.add_argument('--club-no', help='Club Number or ID to import into')
    args = parser.parse_args()
    
    import_meetings(args.file, args.club_no)
