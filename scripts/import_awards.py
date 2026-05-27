import os
import sys
import re
import pandas as pd
from datetime import datetime

# Setup path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.project import Pathway
from app.models.contact import Contact
from app.models.achievement import Achievement
from app.models.user import User

# Traditional awards: exact match on Award Name
TRADITIONAL_AWARDS = {
    "Competent Communicator (CC)": {"path": "Communication Track", "abbr": "TCT", "level": 1},
    "Advanced Communicator Bronze (ACB)": {"path": "Communication Track", "abbr": "TCT", "level": 2},
    "Advanced Communicator Silver (ACS)": {"path": "Communication Track", "abbr": "TCT", "level": 3},
    "Advanced Communicator Gold (ACG)": {"path": "Communication Track", "abbr": "TCT", "level": 4},
    "Competent Leader (CL)": {"path": "Leadership Track", "abbr": "TLT", "level": 1},
    "Advanced Leader Bronze (ALB)": {"path": "Leadership Track", "abbr": "TLT", "level": 2},
    "Advanced Leader Silver (ALS)": {"path": "Leadership Track", "abbr": "TLT", "level": 3},
    "Distinguished Toastmaster (DTM)": {"path": "Distinguished Toastmaster", "abbr": "DTM", "level": None},
    "Distinguished Toastmaster": {"path": "Distinguished Toastmaster", "abbr": "DTM", "level": None},
    "Highest Combined Award": {"path": "Distinguished Toastmaster", "abbr": "DTM", "level": None},
}

# Pathways level pattern: "Pathway Name N (ABBRN)" e.g. "Dynamic Leadership 1 (DL1)"
PATHWAYS_LEVEL_PATTERN = re.compile(r'^(.+?)\s+(\d)\s+\([A-Z]+\d\)$')

# Pathways completion/program awards (no level number)
PATHWAYS_PROGRAM_AWARDS = {
    "Pathways Mentor Program": {"path": None, "type": "program-completion"},
    "DTM Project": {"path": "Distinguished Toastmasters", "type": "program-completion"},
    "Leadership Excellence": {"path": None, "type": "program-completion"},
}


def get_or_create_pathway(name, abbr):
    pathway = Pathway.query.filter_by(name=name).first()
    if not pathway:
        pathway = Pathway(name=name, abbr=abbr, type='traditional')
        db.session.add(pathway)
        db.session.flush()
        print(f"Created pathway: {name}")
    return pathway


def parse_award(award_name):
    """
    Parse an award name and return a dict with keys:
      path_name, level, achievement_type
    Returns None if the award is not recognized.
    """
    # 1. Check traditional awards (exact match)
    if award_name in TRADITIONAL_AWARDS:
        info = TRADITIONAL_AWARDS[award_name]
        ach_type = 'level-completion' if info['level'] is not None else 'program-completion'
        return {
            'path_name': info['path'],
            'level': info['level'],
            'achievement_type': ach_type,
        }

    # 2. Check pathways level awards: e.g. "Dynamic Leadership 1 (DL1)"
    m = PATHWAYS_LEVEL_PATTERN.match(award_name)
    if m:
        path_name = m.group(1).strip()
        level = int(m.group(2))
        # Verify the pathway exists in the database
        pathway = Pathway.query.filter_by(name=path_name).first()
        if pathway:
            return {
                'path_name': path_name,
                'level': level,
                'achievement_type': 'level-completion',
            }

    # 3. Check program awards
    if award_name in PATHWAYS_PROGRAM_AWARDS:
        info = PATHWAYS_PROGRAM_AWARDS[award_name]
        return {
            'path_name': info['path'],
            'level': None,
            'achievement_type': info['type'],
        }

    return None


def import_awards():
    file_path = os.path.join('instance', 'Past and Present Education Awards - May. 27, 2026.xlsx')
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    df = pd.read_excel(file_path, engine='calamine', header=1)
    
    app = create_app()
    with app.app_context():
        # Ensure traditional tracks exist in the database
        for award_info in TRADITIONAL_AWARDS.values():
            get_or_create_pathway(award_info['path'], award_info['abbr'])
        
        db.session.commit()
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            member_id = str(row.get('Member ID')).strip()
            award_name = str(row.get('Award Name')).strip()
            award_date_str = str(row.get('Award Date')).strip()
            
            parsed = parse_award(award_name)
            if not parsed:
                skipped_count += 1
                continue
                
            # Parse date
            try:
                issue_date = pd.to_datetime(award_date_str).date()
            except Exception:
                print(f"Skipping {member_id} {award_name} due to invalid date: {award_date_str}")
                skipped_count += 1
                continue
                
            # Find contact by member_id
            contact = Contact.query.filter_by(Member_ID=member_id).first()
            if not contact:
                skipped_count += 1
                continue
                
            # Check if user is active (has linked user with active status)
            user_id = contact.user_id
            if not user_id:
                skipped_count += 1
                continue
                
            user = db.session.get(User, user_id)
            if not user or user.status != 'active':
                skipped_count += 1
                continue
                
            # Check if achievement already exists
            filters = {
                'user_id': user_id,
                'path_name': parsed['path_name'],
                'achievement_type': parsed['achievement_type'],
            }
            if parsed['level'] is not None:
                filters['level'] = parsed['level']
            
            existing = Achievement.query.filter_by(**filters).first()
            
            if existing:
                # Update issue_date if the Excel has a different (more accurate) date
                if existing.issue_date != issue_date:
                    old_date = existing.issue_date
                    existing.issue_date = issue_date
                    updated_count += 1
                    print(f"Updated {award_name} for {contact.Name}: {old_date} -> {issue_date}")
                else:
                    skipped_count += 1
                continue
                
            # Add new achievement
            ach = Achievement(
                user_id=user_id,
                member_id=member_id,
                issue_date=issue_date,
                achievement_type=parsed['achievement_type'],
                path_name=parsed['path_name'],
                level=parsed['level'],
                notes="Imported from legacy awards file"
            )
            db.session.add(ach)
            added_count += 1
            print(f"Added {award_name} for {contact.Name} on {issue_date}")
            
        db.session.commit()
        print(f"\nDone. Added {added_count}, updated {updated_count}, skipped {skipped_count}.")

if __name__ == '__main__':
    import_awards()
