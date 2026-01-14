"""
Test script to verify Excel formatting is applied correctly.
Run this to generate a test Excel file and verify formatting.
"""

from app import create_app
from app.services.export.service import MeetingExportService
import sys

def test_export_formatting(meeting_number):
    """Test that formatting is applied to exported Excel file."""
    app = create_app()
    
    with app.app_context():
        print(f"Exporting meeting {meeting_number}...")
        output = MeetingExportService.generate_meeting_xlsx(meeting_number)
        
        if output:
            filename = f"test_meeting_{meeting_number}_export.xlsx"
            with open(filename, 'wb') as f:
                f.write(output.getvalue())
            print(f"✅ Export successful: {filename}")
            print("\nPlease verify the following in the Excel file:")
            print("1. Column widths are auto-fitted")
            print("2. Long titles have text wrapping enabled")
            print("3. Long speech objectives have text wrapping")
            print("4. Header rows are bold")
            return True
        else:
            print(f"❌ Export failed - meeting {meeting_number} not found")
            return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        meeting_num = int(sys.argv[1])
    else:
        print("Usage: python test_formatting.py <meeting_number>")
        print("Using default meeting number: 1")
        meeting_num = 1
    
    test_export_formatting(meeting_num)
