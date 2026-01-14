"""
Export service package for generating Excel exports of meeting data.

This package provides a modular structure for exporting meeting information
to Excel format with multiple worksheets including agenda, PowerBI data,
roster, participants, and votes.

Main entry point:
    MeetingExportService.generate_meeting_xlsx(meeting_number)
"""

from .service import MeetingExportService

__all__ = ['MeetingExportService']
