import os
import sys
import re
from datetime import datetime
import uuid
import ast

# Add the app directory to the path so we can import from 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.meeting import Meeting
from app.models.contact import Contact
from app.models.voting import Vote
from app.models.club import Club
from sqlalchemy import func

def extract_insert_values(sql_line):
    """Extracts values from an INSERT INTO statement."""
    # Find the part after "VALUES "
    match = re.search(r'VALUES\s*(.*);?$', sql_line)
    if not match:
        return []

    values_str = match.group(1).strip()
    if values_str.endswith(';'):
        values_str = values_str[:-1]

    # The string contains comma-separated tuples: (1, 953, 'uid', ...), (2, 953, ...)
    # A simple regex isn't perfect for SQL parsing but works for standard dumps
    # It's better to use `ast.literal_eval` if possible, but let's parse it safely
    # Replacing NULL with None for python evaluation
    values_str = values_str.replace('NULL', 'None')
    
    # We can wrap it in a pseudo list string and evaluate it
    try:
        # Evaluate as a tuple of tuples
        parsed_values = ast.literal_eval(f"({values_str})")
        # Ensure it's a list even if there's only one tuple
        if isinstance(parsed_values, tuple) and len(parsed_values) > 0 and not isinstance(parsed_values[0], tuple):
            parsed_values = [parsed_values]
        return list(parsed_values)
    except Exception as e:
        print(f"Error parsing SQL line: {e}")
        return []

def prompt_club():
    clubs = Club.query.all()
    if not clubs:
        print("No clubs found in the database. Exiting.")
        sys.exit(1)

    print("\n--- Available Clubs ---")
    for i, club in enumerate(clubs):
        print(f"{i + 1}. {club.club_name} ({club.club_no})")

    while True:
        try:
            choice = input(f"Select a club (1-{len(clubs)}): ")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(clubs):
                return clubs[choice_idx]
            else:
                print("Invalid selection.")
        except ValueError:
            print("Please enter a valid number.")

def prompt_meetings():
    while True:
        meeting_input = input("Enter meeting number(s) to import (comma-separated, e.g., 958,959): ")
        if not meeting_input.strip():
            print("Meeting input cannot be empty.")
            continue
        try:
            meeting_numbers = [int(num.strip()) for num in meeting_input.split(',')]
            return meeting_numbers
        except ValueError:
            print("Invalid format. Please enter comma-separated numbers.")

def import_voting_data():
    app = create_app()
    with app.app_context():
        # Get inputs
        sql_path = input("Enter path to SQL dump file: ").strip()
        if not sql_path or not os.path.exists(sql_path):
            print("File not found.")
            sys.exit(1)

        selected_club = prompt_club()
        target_meeting_numbers = prompt_meetings()

        # Cache valid meetings for the selected club
        valid_meetings = {}
        for num in target_meeting_numbers:
            meeting = Meeting.query.filter_by(Meeting_Number=num, club_id=selected_club.id).first()
            if meeting:
                valid_meetings[num] = meeting
            else:
                print(f"Warning: Meeting #{num} not found or does not belong to the selected club.")

        if not valid_meetings:
            print("No valid meetings found to process. Exiting.")
            sys.exit(1)

        print(f"\nProcessing SQL file: {sql_path}")
        print(f"Target Meetings: {', '.join(map(str, valid_meetings.keys()))}")

        row_count = 0
        vote_count = 0
        meetings_to_update = {}

        # Questions for NPS and Feedback (matching app/voting_routes.py)
        NPS_QUESTION = "How likely are you to recommend this meeting to a friend or colleague?"

        # Extract Contact mappings from SQL Dump
        old_contact_mapping = {}
        with open(sql_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith("INSERT INTO `Contacts`"):
                    matches = re.finditer(r"\(([0-9]+),'((?:[^']|'')*)'", line)
                    for match in matches:
                        c_id = int(match.group(1))
                        name = match.group(2).replace("''", "'")
                        old_contact_mapping[c_id] = name
                    break
        
        # Build mapping of Name -> New Contact ID in the current DB
        current_contacts = Contact.query.order_by(Contact.id).all()
        name_to_new_contact_id = {}
        for c in current_contacts:
            if c.Name not in name_to_new_contact_id:
                name_to_new_contact_id[c.Name] = c.id

        with open(sql_path, 'r', encoding='utf-8') as f:
            for line_number, line in enumerate(f, start=1):
                if line.startswith("INSERT INTO `votes`"):
                    print(f"Found INSERT statement at line {line_number}")
                    records = extract_insert_values(line)
                    
                    for record in records:
                        # Expected format:
                        # 0: id, 1: meeting_number, 2: voter_identifier, 3: award_category, 
                        # 4: contact_id, 5: question, 6: score, 7: comments
                        if len(record) < 8:
                            continue

                        _, meeting_num, voter_id, award_cat, old_contact_id, question, score, comments = record

                        if meeting_num in valid_meetings:
                            meeting = valid_meetings[meeting_num]
                            meetings_to_update[meeting_num] = meeting

                            # Convert contact_id
                            contact_id = None
                            if old_contact_id is not None:
                                old_name = old_contact_mapping.get(old_contact_id)
                                if old_name:
                                    contact_id = name_to_new_contact_id.get(old_name)
                                    if not contact_id:
                                        print(f"Warning: Contact '{old_name}' (ID {old_contact_id}) not found in current Database. Target ID set to None.")
                                else:
                                    print(f"Warning: Old contact ID {old_contact_id} not found in SQL dump's Contacts table.")

                            # Ensure score is integer if present
                            score_val = None
                            if score is not None:
                                try:
                                    score_val = int(score)
                                except ValueError:
                                    pass

                            vote = Vote(
                                meeting_id=meeting.id,
                                voter_identifier=voter_id,
                                award_category=award_cat,
                                contact_id=contact_id,
                                question=question,
                                score=score_val,
                                comments=comments
                            )
                            db.session.add(vote)
                            vote_count += 1
                        
                        row_count += 1

        db.session.commit()
        print(f"Imported {vote_count} vote records out of {row_count} total rows in INSERT.")

        print(f"Updating winners and NPS for {len(meetings_to_update)} meetings...")

        # Update meeting winners and NPS
        for meeting_num, meeting in meetings_to_update.items():
            # Tally votes for winners
            # We group by category and contact_id to find the person with the most votes in each category
            vote_counts = db.session.query(
                Vote.award_category,
                Vote.contact_id,
                func.count(Vote.id).label('vote_count')
            ).filter(Vote.meeting_id == meeting.id)\
             .filter(Vote.award_category.isnot(None))\
             .group_by(Vote.award_category, Vote.contact_id)\
             .all()

            winners = {} # {category: (contact_id, count)}
            for category, contact_id, count in vote_counts:
                if category not in winners or count > winners[category][1]:
                    winners[category] = (contact_id, count)

            # Pre-fetch session types to help create records if missing
            from app.models.session import SessionType, SessionLog, OwnerMeetingRoles

            speaker_id = winners.get('speaker', (None, 0))[0]
            evaluator_id = winners.get('evaluator', (None, 0))[0]
            role_taker_id = winners.get('role-taker', (None, 0))[0]
            table_topic_id = winners.get('table-topic', (None, 0))[0]
            
            # Map of categories to our standard session types to backfill if missing
            # (In a real system we'd look up the exact role id, but this guarantees voting picks it up)
            category_mapping = {
                'speaker': speaker_id,
                'evaluator': evaluator_id,
                'role-taker': role_taker_id, 
                'table-topic': table_topic_id
            }

            for cat, c_id in category_mapping.items():
                if c_id:
                    # Quick heuristic to find a SessionType related to this category via role name matching
                    st_search_terms = {
                        'speaker': 'Prepared Speaker',
                        'evaluator': 'Individual Evaluator',
                        'role-taker': 'Ah-Counter', # fallback for any role-taker
                        'table-topic': 'Topics Speaker'
                    }
                    search_term = st_search_terms[cat]
                    
                    # Ensure we only pick session types that actually have an associated role.
                    st = SessionType.query.filter(
                        SessionType.Title.like(f"%{search_term}%"),
                        SessionType.role_id.isnot(None),
                        SessionType.club_id.in_([None, meeting.club_id])
                    ).first()
                    
                    if st and st.role:
                        # Check if this contact is already assigned to this meeting role
                        existing_omr = OwnerMeetingRoles.query.filter_by(
                            meeting_id=meeting.id,
                            contact_id=c_id,
                            role_id=st.role_id
                        ).first()
                        
                        if not existing_omr:
                            print(f"Adding missing session role config for {cat} -> contact {c_id}")
                            try:
                                from app.services.role_service import RoleService
                                RoleService.assign_role(meeting.id, meeting.club_id, c_id, st.role_id, {})
                            except Exception as e:
                                print(f"Error assigning {cat} role: {e}")

            # Update meeting attributes
            # Defaults to None if no winner found (all unrecognized or no votes)
            meeting.best_speaker_id = speaker_id
            meeting.best_evaluator_id = evaluator_id
            meeting.best_role_taker_id = role_taker_id
            meeting.best_table_topic_id = table_topic_id

            # Tally NPS (Average of scores for the NPS question)
            nps_avg = db.session.query(func.avg(Vote.score)).filter(
                Vote.meeting_id == meeting.id,
                Vote.question == NPS_QUESTION,
                Vote.score.isnot(None)
            ).scalar()

            if nps_avg is not None:
                meeting.nps = float(nps_avg)
            
            print(f"Meeting #{meeting_num} ({meeting.Meeting_Date}): NPS={meeting.nps if meeting.nps is not None else 'N/A'}")

        db.session.commit()
        print("Successfully updated meeting records. Import complete.")

if __name__ == "__main__":
    try:
        import_voting_data()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)
