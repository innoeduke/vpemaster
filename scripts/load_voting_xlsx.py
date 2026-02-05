import os
import sys
from datetime import datetime
import uuid
import openpyxl
from sqlalchemy import func

# Add the app directory to the path so we can import from 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.meeting import Meeting
from app.models.contact import Contact
from app.models.voting import Vote

def load_voting_data(file_path):
    app = create_app()
    with app.app_context():
        print(f"Opening {file_path}...")
        try:
            wb = openpyxl.load_workbook(file_path)
        except Exception as e:
            print(f"Error opening workbook: {e}")
            return
            
        sheet = wb.active
        
        # Mapping names to IDs to avoid repeated lookups
        contact_cache = {}
        def get_contact_id(name):
            if not name or str(name).strip().lower() in ['nan', 'None', ''] or str(name).strip() == '':
                return None
            name = str(name).strip()
            if name in contact_cache:
                return contact_cache[name]
            
            # Simple lookup by name.
            contact = Contact.query.filter(Contact.Name == name).first()
            if contact:
                contact_cache[name] = contact.id
                return contact.id
            return None

        # Determine meetings to update at the end
        meetings_to_update = {}

        # Questions for NPS and Feedback (matching app/voting_routes.py)
        NPS_QUESTION = "How likely are you to recommend this meeting to a friend or colleague?"
        FEEDBACK_QUESTION = "More feedback/comments"

        print("Processing rows...")
        row_count = 0
        vote_count = 0
        
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            # Columns: 0:date, 1:speaker, 2:evaluator, 3:role-taker, 4:table-topic, 5:score, 6:comments
            if len(row) < 7:
                print(f"Row {row_idx}: Insufficient columns (found {len(row)})")
                continue
                
            meeting_date, best_speaker, best_evaluator, best_role_taker, best_table_topics, score, comments = row[:7]
            
            if not meeting_date:
                continue
                
            # Normalize meeting_date
            if isinstance(meeting_date, str):
                try:
                    # Try common formats if string
                    meeting_date = datetime.strptime(meeting_date, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        meeting_date = datetime.strptime(meeting_date, '%m/%d/%Y').date()
                    except ValueError:
                        try:
                            meeting_date = datetime.strptime(meeting_date, '%Y/%m/%d').date()
                        except ValueError:
                            print(f"Row {row_idx}: Invalid date format {meeting_date}")
                            continue
            elif isinstance(meeting_date, datetime):
                meeting_date = meeting_date.date()

            # Lookup meeting by date
            meeting = Meeting.query.filter_by(Meeting_Date=meeting_date).first()
            if not meeting:
                # print(f"Row {row_idx}: Meeting not found for date {meeting_date}")
                continue
            
            meeting_number = meeting.Meeting_Number
            if meeting_number not in meetings_to_update:
                meetings_to_update[meeting_number] = meeting

            voter_identifier = str(uuid.uuid4())
            
            # Award categories mapping
            # Note: columns 1-4 correspond to award categories
            category_mapping = {
                'speaker': best_speaker,
                'evaluator': best_evaluator,
                'role-taker': best_role_taker,
                'table-topic': best_table_topics
            }

            for category, winner_name in category_mapping.items():
                contact_id = get_contact_id(winner_name)
                if contact_id:
                    vote = Vote(
                        meeting_number=meeting_number,
                        voter_identifier=voter_identifier,
                        award_category=category,
                        contact_id=contact_id
                    )
                    db.session.add(vote)
                    vote_count += 1

            # NPS Score
            try:
                score_val = int(score) if score is not None and str(score).strip() != '' else 0
            except ValueError:
                score_val = 0
            
            nps_vote = Vote(
                meeting_number=meeting_number,
                voter_identifier=voter_identifier,
                question=NPS_QUESTION,
                score=score_val
            )
            db.session.add(nps_vote)
            vote_count += 1

            # Comments
            if comments and str(comments).strip():
                comment_vote = Vote(
                    meeting_number=meeting_number,
                    voter_identifier=voter_identifier,
                    question=FEEDBACK_QUESTION,
                    comments=str(comments).strip()
                )
                db.session.add(comment_vote)
                vote_count += 1
            
            row_count += 1

        db.session.commit()
        print(f"Imported {row_count} rows ({vote_count} vote records).")
        print(f"Updating winners and NPS for {len(meetings_to_update)} meetings...")

        # Update meeting winners and NPS
        for meeting_num, meeting in meetings_to_update.items():
            # Tally votes for winners
            # We group by category and contact_id to find the person with the most votes in each category
            vote_counts = db.session.query(
                Vote.award_category,
                Vote.contact_id,
                func.count(Vote.id).label('vote_count')
            ).filter(Vote.meeting_number == meeting_num)\
             .filter(Vote.award_category.isnot(None))\
             .group_by(Vote.award_category, Vote.contact_id)\
             .all()

            winners = {} # {category: (contact_id, count)}
            for category, contact_id, count in vote_counts:
                if category not in winners or count > winners[category][1]:
                    winners[category] = (contact_id, count)

            # Update meeting attributes
            # Defaults to None if no winner found (all unrecognized or no votes)
            meeting.best_speaker_id = winners.get('speaker', (None, 0))[0]
            meeting.best_evaluator_id = winners.get('evaluator', (None, 0))[0]
            meeting.best_role_taker_id = winners.get('role-taker', (None, 0))[0]
            meeting.best_table_topic_id = winners.get('table-topic', (None, 0))[0]

            # Tally NPS (Average of scores for the NPS question)
            nps_avg = db.session.query(func.avg(Vote.score)).filter(
                Vote.meeting_number == meeting_num,
                Vote.question == NPS_QUESTION,
                Vote.score.isnot(None)
            ).scalar()

            if nps_avg is not None:
                meeting.nps = float(nps_avg)
            
            print(f"Meeting #{meeting_num} ({meeting.Meeting_Date}): NPS={meeting.nps if meeting.nps is not None else 'N/A'}")

        db.session.commit()
        print("Successfully updated meeting records. Import complete.")

if __name__ == "__main__":
    # The file path as specified by the user
    instance_file_path = "instance/voting.xlsx"
    
    # Resolve absolute path relative to script location (assuming scripts/load_voting_xlsx.py)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    full_path = os.path.join(base_dir, instance_file_path)
    
    if not os.path.exists(full_path):
        print(f"Error: {instance_file_path} not found at {full_path}")
    else:
        load_voting_data(full_path)
