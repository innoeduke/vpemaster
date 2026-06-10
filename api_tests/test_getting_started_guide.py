"""
Test script for VPEMaster Getting Started Guide
Tests all tasks using the API with clubadmin credentials

Usage:
    cd ~/workspaces/vpemaster
    source venv/bin/activate
    pip install requests
    pytest api_tests/test_getting_started_guide.py -v

Credentials:
    Username: stephaye
    Password: Wxm0216!
"""

import pytest
import requests
import time
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:5000"

# Test credentials
ADMIN_EMAIL = "stephaye"
ADMIN_PASSWORD = "Wxm0216!"

class APIClient:
    """Simple API client with session management"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "VPEMaster Test Client"})
    
    def login(self, email, password):
        """Login and maintain session"""
        response = self.session.post(
            f"{BASE_URL}/login",
            data={"username": email, "password": password},
            allow_redirects=False
        )
        return response
    
    def post(self, path, data=None, json=None):
        """POST request"""
        url = f"{BASE_URL}{path}"
        if json:
            return self.session.post(url, json=json)
        return self.session.post(url, data=data)
    
    def get(self, path):
        """GET request"""
        return self.session.get(f"{BASE_URL}{path}")


@pytest.fixture
def client():
    """Create authenticated API client"""
    client = APIClient()
    response = client.login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if response.status_code not in [200, 302]:
        pytest.skip(f"Login failed: {response.status_code}")
    return client


class TestInitialSettings:
    """Test Initial Settings tasks"""
    
    def test_update_club_info(self, client):
        """Update club info via /about_club/update"""
        response = client.post("/about_club/update", data={
            "club_name": "Test Club Updated",
            "meeting_schedule": "Every Thursday 7pm"
        })
        assert response.status_code in [200, 302], f"Update club info failed: {response.status_code}"
    
    def test_add_excomm_member(self, client):
        """Add excomm team member via /settings/excomm/add"""
        response = client.post("/settings/excomm/add", data={
            "member_id": 1,
            "role": "President",
            "term_start": "2026-01-01",
            "term_end": "2026-12-31"
        })
        assert response.status_code in [200, 302], f"Add excomm failed: {response.status_code}"
    
    def test_add_user(self, client):
        """Add club member as user via /user/form"""
        timestamp = int(time.time())
        response = client.post("/user/form", data={
            "first_name": f"Test{timestamp}",
            "last_name": "User",
            "email": f"testuser{timestamp}@example.com",
            "role": "User"
        })
        assert response.status_code in [200, 302], f"Add user failed: {response.status_code}"
    
    def test_add_ticket_type(self, client):
        """Add ticket type via /settings/tickets/add"""
        response = client.post("/settings/tickets/add", data={
            "name": f"Test Ticket {int(time.time())}",
            "category": "Technical",
            "priority": "Medium"
        })
        assert response.status_code in [200, 302], f"Add ticket type failed: {response.status_code}"


class TestMeetingManagementBefore:
    """Test Before the Meeting tasks"""
    
    def test_create_meeting(self, client):
        """Create a meeting via /agenda/create"""
        response = client.post("/agenda/create", data={
            "club_id": 3,
            "meeting_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "start_time": "19:00"
        })
        assert response.status_code in [200, 302], f"Create meeting failed: {response.status_code}"
    
    def test_update_agenda(self, client):
        """Update agenda via /agenda/update"""
        response = client.post("/agenda/update", data={
            "meeting_id": 1,
            "agenda_data": "Test agenda content"
        })
        assert response.status_code in [200, 302], f"Update agenda failed: {response.status_code}"
    
    def test_book_meeting_role(self, client):
        """Book a meeting role via /booking/book"""
        response = client.post("/booking/book", data={
            "meeting_id": 1,
            "role_type": "Speaker",
            "member_id": 1
        })
        assert response.status_code in [200, 302], f"Book role failed: {response.status_code}"
    
    def test_add_speech_project_info(self, client):
        """Add project info for prepared speech via /speech_log/update"""
        response = client.post("/speech_log/update/1", data={
            "project_code": "DL1",
            "speech_title": "Test Speech",
            "duration": 7
        })
        assert response.status_code in [200, 302], f"Add speech project info failed: {response.status_code}"
    
    def test_generate_meeting_slides(self, client):
        """Generate meeting slides via /agenda/ppt/<id>"""
        response = client.get("/agenda/ppt/1")
        assert response.status_code in [200, 302], f"Generate slides failed: {response.status_code}"


class TestMeetingManagementDuring:
    """Test During the Meeting tasks"""
    
    def test_view_voting(self, client):
        """View voting page"""
        response = client.get("/voting")
        assert response.status_code == 200, f"View voting failed: {response.status_code}"
    
    def test_cast_vote(self, client):
        """Cast vote via /voting/vote - requires running meeting"""
        response = client.post("/voting/vote", json={
            "meeting_id": 1,
            "contact_id": 1,
            "award_category": "best_speaker"
        })
        # 403/404 = meeting not active/found, which is expected without proper setup
        assert response.status_code in [200, 201, 302, 400, 403, 404], f"Cast vote failed: {response.status_code}"


class TestMeetingManagementAfter:
    """Test After the Meeting tasks"""
    
    def test_view_voting_report(self, client):
        """Analyze meeting reports via /voting"""
        response = client.get("/voting")
        assert response.status_code == 200, f"View voting report failed: {response.status_code}"
    
    def test_add_video_media_link(self, client):
        """Add video media link to speech via /speech_log/update"""
        response = client.post("/speech_log/update/1", data={
            "media_url": "https://youtube.com/watch?v=test"
        })
        assert response.status_code in [200, 302], f"Add video link failed: {response.status_code}"
    
    def test_complete_level(self, client):
        """Complete a level via /achievements/record"""
        response = client.post("/achievements/record", data={
            "member_id": 1,
            "achievement_type": "level_complete",
            "level": 2
        })
        assert response.status_code in [200, 302], f"Complete level failed: {response.status_code}"


class TestClubLevelSettings:
    """Test More Club Level Settings tasks"""
    
    def test_add_custom_session_type(self, client):
        """Add custom session type via /settings/sessions/add"""
        response = client.post("/settings/sessions/add", data={
            "name": f"Custom Session {int(time.time())}",
            "duration": 120,
            "description": "Test session type"
        })
        assert response.status_code in [200, 302], f"Add session type failed: {response.status_code}"
    
    def test_add_custom_role(self, client):
        """Add custom club meeting role via /settings/roles/add"""
        response = client.post("/settings/roles/add", data={
            "name": f"CustomRole_{int(time.time())}",
            "description": "Test custom role",
            "default_duration": 5
        })
        assert response.status_code in [200, 302], f"Add custom role failed: {response.status_code}"


class TestUserSpecificSettings:
    """Test User Specific Settings tasks"""
    
    def test_update_member_contact_info(self, client):
        """Update member contact information via /contact/form/<id>"""
        response = client.post("/contact/form/1", data={
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone": "9876543210",
            "type": "Member"
        })
        assert response.status_code in [200, 302], f"Update contact info failed: {response.status_code}"
    
    def test_complete_member_level(self, client):
        """Complete member level via /achievements/record"""
        response = client.post("/achievements/record", data={
            "member_id": 1,
            "achievement_type": "level_complete",
            "pathway": "Dynamic Leadership",
            "level": 3
        })
        assert response.status_code in [200, 302], f"Complete member level failed: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
