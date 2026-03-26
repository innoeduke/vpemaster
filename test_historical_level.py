import os
import sys
from datetime import date, timedelta

# Add the application directory to the path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models.contact import Contact
from app.models.achievement import Achievement
from app.models.meeting import Meeting
from app.models.session import SessionLog, SessionType
from app.models.roster import MeetingRole
from app.models.project import Pathway

def test_historical_level():
    app = create_app()
    with app.app_context():
        # 1. Setup Mock Pathway
        pathway_name = "Dynamic Leadership"
        path = Pathway.query.filter_by(name=pathway_name).first()
        if not path:
            print("Pathway not found")
            return

        # 2. Setup Mock Role
        timer_role = MeetingRole.query.filter_by(name='Timer').first()
        if not timer_role:
            print("Timer role not found")
            return
        
        # 3. Setup Mock Contact (ID 55 - Caoimhe)
        contact = db.session.get(Contact, 55)
        if not contact:
            print("Contact 55 not found")
            return
        
        print(f"Testing for Contact: {contact.Name}")
        print(f"Current Path: {contact.Current_Path}")

        # Test Case 1: No achievements, meeting date today
        today = date.today()
        # Clear any cached achievements for clean test
        if hasattr(contact, f'_achievements_{pathway_name}'):
            delattr(contact, f'_achievements_{pathway_name}')
        
        level = contact.get_active_level_at_date(pathway_name, today)
        print(f"Scenario 1 (No Achievements, Date {today}): Level {level} (Expected: 1)")
        assert level == 1

        # Test Case 2: Level 1 completed last week, meeting date today
        last_week = today - timedelta(days=7)
        mock_achievement = Achievement(
            user_id=contact.user_id,
            achievement_type='level-completion',
            path_name=pathway_name,
            level=1,
            issue_date=last_week
        )
        # We won't actually commit this to DB for safety, just mock the cache
        # Use the correct key (with space as in pathway_name)
        setattr(contact, f'_achievements_{pathway_name}', [mock_achievement])
        
        level = contact.get_active_level_at_date(pathway_name, today)
        print(f"Scenario 2 (L1 done {last_week}, Date {today}): Level {level} (Expected: 2)")
        assert level == 2

        # Test Case 3: Level 1 completed last week, meeting date 10 days ago
        ten_days_ago = today - timedelta(days=10)
        level = contact.get_active_level_at_date(pathway_name, ten_days_ago)
        print(f"Scenario 3 (L1 done {last_week}, Date {ten_days_ago}): Level {level} (Expected: 1)")
        assert level == 1

        # Test Case 4: Level 1 completed TODAY, meeting date TODAY
        # Toastmasters rule: same day counts for the level being completed
        setattr(contact, f'_achievements_{pathway_name}', [
            Achievement(user_id=contact.user_id, achievement_type='level-completion', path_name=pathway_name, level=1, issue_date=today)
        ])
        level = contact.get_active_level_at_date(pathway_name, today)
        print(f"Scenario 4 (L1 done {today}, Date {today}): Level {level} (Expected: 1)")
        assert level == 1

        print("\nAll Scenarios Passed!")

if __name__ == "__main__":
    test_historical_level()
