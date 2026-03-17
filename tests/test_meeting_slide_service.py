import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import io
from flask import Flask
from app.services.meeting_slide_service import MeetingSlideService

class TestMeetingSlideService(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['STATIC_FOLDER'] = 'static'
        self.app.static_folder = 'static'
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('app.services.meeting_slide_service.MeetingExportContext')
    @patch('app.services.meeting_slide_service.Presentation')
    @patch('os.path.exists')
    def test_generate_meeting_pptx_success(self, mock_exists, mock_presentation, mock_context_cls):
        # Mock Meeting
        mock_meeting = Mock()
        mock_meeting.Meeting_Number = 100
        mock_meeting.Meeting_Date = Mock()
        mock_meeting.Meeting_Date.strftime.return_value = "16-Mar-2026"
        mock_meeting.club_id = 1
        mock_meeting.club.club_name = "Test Club"
        mock_meeting.get_excomm.return_value = None
        
        # Mock Context
        mock_context = mock_context_cls.return_value
        mock_context.meeting = mock_meeting
        mock_context.logs = []
        mock_context.speech_details = {}
        
        # Mock Template Path
        mock_exists.return_value = True
        
        # Mock Presentation
        mock_prs = mock_presentation.return_value
        mock_prs.slides = []
        
        # Run service
        result = MeetingSlideService.generate_meeting_pptx(1)
        
        # Assertions
        self.assertIsNotNone(result)
        mock_presentation.assert_called_once()
        mock_prs.save.assert_called_once()

    @patch('app.services.meeting_slide_service.MeetingExportContext')
    def test_generate_meeting_pptx_no_meeting(self, mock_context_cls):
        mock_context = mock_context_cls.return_value
        mock_context.meeting = None
        
        result = MeetingSlideService.generate_meeting_pptx(1)
        self.assertIsNone(result)

    def test_initialize_placeholders(self):
        mock_meeting = Mock()
        mock_meeting.Meeting_Number = 100
        mock_meeting.Meeting_Date.strftime.return_value = "16-Mar-2026"
        mock_meeting.club.club_name = "Test Club"
        
        replacements = MeetingSlideService._initialize_placeholders(mock_meeting)
        
        self.assertEqual(replacements["{{meeting_number}}"], "100")
        self.assertEqual(replacements["{{club_name}}"], "Test Club")
        self.assertIn("{{saa_info}}", replacements)

if __name__ == '__main__':
    unittest.main()
