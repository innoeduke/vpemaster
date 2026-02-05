
from datetime import time, date, datetime, timedelta
from unittest.mock import MagicMock, patch
import pytest

# Mock models locally for this test
class MockSessionLog:
    def __init__(self, id, Meeting_Number, Meeting_Seq, Duration_Max, hidden=None, Type_ID=None):
        self.id = id
        self.Meeting_Number = Meeting_Number
        self.Meeting_Seq = Meeting_Seq
        self.Duration_Max = Duration_Max
        self.hidden = hidden
        self.Start_Time = None
        self.Type_ID = Type_ID

class MockSessionType:
    def __init__(self, id, Title, Is_Section, Is_Hidden):
        self.id = id
        self.Title = Title
        self.Is_Section = Is_Section
        self.Is_Hidden = Is_Hidden
    
    @staticmethod
    def get_id_by_title(title, club_id):
        if title == 'Evaluation': return 31
        return 99

class MockMeeting:
    def __init__(self, Meeting_Number, Meeting_Date, Start_Time, club_id=1, ge_mode=0):
        self.Meeting_Number = Meeting_Number
        self.Meeting_Date = Meeting_Date
        self.Start_Time = Start_Time
        self.club_id = club_id
        self.ge_mode = ge_mode

def test_recalculate_start_times(app):
    # Import inside function to avoid module-level side effects if any, 
    # though with real app fixture it should be fine.
    try:
        from app.agenda_routes import _recalculate_start_times
        from app.models import SessionType
    except ImportError:
        pytest.skip("Could not import app.agenda_routes")
    
    meeting = MockMeeting(1, date(2026, 2, 5), time(19, 0))
    
    # Types
    type_sect = MockSessionType(1, 'Section', True, False)
    type_norm = MockSessionType(2, 'Normal', False, False)
    type_hidden = MockSessionType(3, 'Hidden Type', False, True)
    
    # Logs
    log1 = MockSessionLog(1, 1, 1, 0) # Section
    log2 = MockSessionLog(2, 1, 2, 5) # Normal 5m
    log3 = MockSessionLog(3, 1, 3, 10, hidden=True) # Hidden override 10m
    log4 = MockSessionLog(4, 1, 4, 15) # Normal 15m
    log5 = MockSessionLog(5, 1, 5, 20) # Type hidden 20m
    log6 = MockSessionLog(6, 1, 6, 25) # Normal 25m
    
    # Setup mock query
    mock_logs = [
        (log1, True, False), # log, is_section, is_hidden_type
        (log2, False, False),
        (log3, False, False),
        (log4, False, False),
        (log5, False, True),
        (log6, False, False),
    ]
    
    # We need to patch the db query used inside _recalculate_start_times
    # AND likely the SessionType model usage if it uses it directly.
    with patch('app.agenda_routes.db.session.query') as mock_query, \
         patch('app.agenda_routes.SessionType') as mock_st_model:
        
        mock_query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = mock_logs
        
        # Determine if real SessionType or Mock is used. 
        # The code probably calls SessionType.get_id_by_title.
        # We can just set the side_effect to our local Mock method.
        mock_st_model.get_id_by_title.side_effect = MockSessionType.get_id_by_title
        
        _recalculate_start_times([meeting])
        
        # Assertions
        assert log1.Start_Time is None
        assert log2.Start_Time == time(19, 0)
        assert log3.Start_Time is None
        assert log4.Start_Time == time(19, 6)
        assert log5.Start_Time is None
        assert log6.Start_Time == time(19, 22)

