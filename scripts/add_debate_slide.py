import os
import sys
from flask import Flask

# Add app directory to path
sys.path.append('/Users/wmu/workspace/toastmasters/vpemaster')

from app.services.meeting_slide_service import MeetingSlideService

app = Flask(__name__)
# Mock static folder
app.static_folder = '/Users/wmu/workspace/toastmasters/vpemaster/app/static'

with app.app_context():
    club_id = 2
    slide_title = ""
    num_roles = 3 
    meeting_type = "Panel Discussion"
    host = {
        'name': '',
        'credential': '',
        'role': 'Moderator',
        'avatar-url': ''
    }
    
    extra_contacts = [
        {'name': f'Speaker {i+1}', 'role': 'Panelist', 'avatar-url': ''}
        for i in range(num_roles)
    ]
    
    duration_info = "{{debate_duration}}"
    
    print(f"Adding Event template slide for Club {club_id} using contact objects...")
    success = MeetingSlideService.add_event_template_slide(
        club_id=club_id,
        slide_title=slide_title,
        host=host,
        extra_contacts=extra_contacts,
        duration_info=duration_info,
        event_type=meeting_type,
        slide_number=3 # Position at the beginning
    )
    
    if success:
        print("Successfully added event template slide to slides_template.pptx!")
    else:
        print("Failed to add event template slide.")
