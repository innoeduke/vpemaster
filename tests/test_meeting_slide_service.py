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

    @patch('app.agenda_routes._get_processed_logs_data')
    @patch('app.services.meeting_slide_service.Meeting')
    @patch('app.services.meeting_slide_service.Contact')
    @patch('app.services.meeting_slide_service.MeetingExportContext')
    @patch('app.services.meeting_slide_service.Presentation')
    @patch('os.path.exists')
    @patch('app.services.meeting_slide_service.db')
    def test_generate_meeting_pptx_success(self, mock_db, mock_exists, mock_presentation, mock_context_cls, mock_contact_model, mock_meeting_model, mock_get_logs):
        # Mock logs data
        mock_get_logs.return_value = ([], None)
        
        # Mock Meeting
        mock_meeting = Mock()
        mock_meeting.Meeting_Number = 100
        mock_meeting.Meeting_Date = Mock()
        mock_meeting.Meeting_Date.strftime.return_value = "16-Mar-2026"
        mock_meeting.club_id = 1
        mock_meeting.club.club_name = "Test Club"
        mock_meeting.get_excomm.return_value = None
        
        # Mock db.session.get
        mock_contact = Mock()
        mock_db.session.get.side_effect = lambda model, pk: mock_meeting if model == mock_meeting_model else mock_contact
        
        # Mock Contact Model Query (legacy fallback)
        mock_contact_model.query.get.return_value = mock_contact
        
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

    @patch('app.services.meeting_slide_service.Meeting')
    @patch('app.services.meeting_slide_service.MeetingExportContext')
    @patch('app.services.meeting_slide_service.db')
    def test_generate_meeting_pptx_no_meeting(self, mock_db, mock_context_cls, mock_meeting_model):
        mock_db.session.get.return_value = None
        mock_context = mock_context_cls.return_value
        mock_context.meeting = None
        
        result = MeetingSlideService.generate_meeting_pptx(1)
        self.assertIsNone(result)

    @patch('app.services.meeting_slide_service.Meeting')
    @patch('app.services.meeting_slide_service.Contact')
    @patch('app.services.meeting_slide_service.Presentation')
    @patch('os.path.exists')
    @patch('app.services.meeting_slide_service.db')
    def test_generate_meeting_pptx_v2_officer_and_section_logic(self, mock_db, mock_exists, mock_presentation, mock_contact_model, mock_meeting_model):
        # Mock Meeting
        mock_meeting = Mock()
        mock_meeting.Meeting_Number = 100
        mock_meeting.Meeting_Date = Mock()
        mock_meeting.Meeting_Date.strftime.return_value = "16-Mar-2026"
        mock_meeting.club_id = 1
        mock_meeting.club.club_name = "Test Club"
        
        # Mock db.session.get
        mock_db.session.get.return_value = mock_meeting
        
        # Mock MeetingRoles returned by db.session.query().filter_by().all()
        mock_role_president = Mock()
        mock_role_president.name = "President"
        mock_role_president.type = "officer"
        
        mock_query = Mock()
        mock_query.filter_by.return_value.all.side_effect = [[mock_role_president], []] # Global, then Local
        mock_db.session.query.return_value = mock_query

        # Mock template slide layouts
        layout_title = Mock()
        layout_title.name = 'Title Slide'
        
        layout_action = Mock()
        layout_action.name = 'section_action'
        
        layout_roletaker = Mock()
        layout_roletaker.name = 'Role Taker Slide'
        
        layout_president_1 = Mock()
        layout_president_1.name = 'President_1'
        
        layout_president_2 = Mock()
        layout_president_2.name = 'President_2'
        
        layout_voting = Mock()
        layout_voting.name = 'section_voting'
        
        mock_prs = mock_presentation.return_value
        mock_prs.slide_layouts = [
            layout_title,
            layout_roletaker,
            layout_president_1,
            layout_president_2,
            layout_voting,
            layout_action
        ]
        
        mock_exists.return_value = True
        
        # Mock logs data: SAA/President (officer) and a section log
        logs_data = [
            {
                "Session_Title": "AWARDS & CLOSING",
                "is_section": True,
                "Duration_Max": 0
            },
            {
                "Session_Title": "President's Address",
                "role": "President",
                "session_type_title": "Generic",
                "Duration_Min": 2,
                "Duration_Max": 3,
                "is_section": False
            }
        ]
        
        # Run service
        result = MeetingSlideService.generate_meeting_pptx_v2(1, logs_data)
        
        # Assertions
        self.assertIsNotNone(result)
        
        # Verify the order of add_slide calls
        # Expected: Title Slide, section_action, Role Taker Slide, President_1, President_2, section_voting
        expected_layout_names = [
            'Title Slide',
            'section_action',
            'Role Taker Slide',
            'President_1',
            'President_2',
            'section_voting'
        ]
        
        added_layouts = [call[0][0].name for call in mock_prs.slides.add_slide.call_args_list]
        self.assertEqual(added_layouts, expected_layout_names)

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
