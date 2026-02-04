
import sys
import os

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import time, date, datetime, timedelta
from unittest.mock import MagicMock, patch

# Mock Flask and SQLAlchemy before importing agenda_routes
sys.modules['flask'] = MagicMock()
sys.modules['flask_login'] = MagicMock()
mock_db = MagicMock()
sys.modules['app'] = MagicMock()
sys.modules['app'].db = mock_db

# Mock models
class SessionLog:
    def __init__(self, id, Meeting_Number, Meeting_Seq, Duration_Max, hidden=None, Type_ID=None):
        self.id = id
        self.Meeting_Number = Meeting_Number
        self.Meeting_Seq = Meeting_Seq
        self.Duration_Max = Duration_Max
        self.hidden = hidden
        self.Start_Time = None
        self.Type_ID = Type_ID

class SessionType:
    def __init__(self, id, Title, Is_Section, Is_Hidden):
        self.id = id
        self.Title = Title
        self.Is_Section = Is_Section
        self.Is_Hidden = Is_Hidden
    
    @staticmethod
    def get_id_by_title(title, club_id):
        if title == 'Evaluation': return 31
        return 99

class Meeting:
    def __init__(self, Meeting_Number, Meeting_Date, Start_Time, club_id=1, ge_mode=0):
        self.Meeting_Number = Meeting_Number
        self.Meeting_Date = Meeting_Date
        self.Start_Time = Start_Time
        self.club_id = club_id
        self.ge_mode = ge_mode

# Mock constants
class MockConstants:
    GLOBAL_CLUB_ID = 1

import app
app.constants = MockConstants

# Import the function to test
from app.agenda_routes import _recalculate_start_times

def test_recalculate_start_times():
    meeting = Meeting(1, date(2026, 2, 5), time(19, 0))
    
    # Types
    type_sect = SessionType(1, 'Section', True, False)
    type_norm = SessionType(2, 'Normal', False, False)
    type_hidden = SessionType(3, 'Hidden Type', False, True)
    
    # Logs
    log1 = SessionLog(1, 1, 1, 0) # Section
    log2 = SessionLog(2, 1, 2, 5) # Normal 5m
    log3 = SessionLog(3, 1, 3, 10, hidden=True) # Hidden override 10m
    log4 = SessionLog(4, 1, 4, 15) # Normal 15m
    log5 = SessionLog(5, 1, 5, 20) # Type hidden 20m
    log6 = SessionLog(6, 1, 6, 25) # Normal 25m
    
    # Setup mock query
    mock_logs = [
        (log1, True, False), # log, is_section, is_hidden_type
        (log2, False, False),
        (log3, False, False),
        (log4, False, False),
        (log5, False, True),
        (log6, False, False),
    ]
    
    with patch('app.agenda_routes.db.session.query') as mock_query, \
         patch('app.agenda_routes.SessionType') as mock_st_model:
        
        mock_query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = mock_logs
        mock_st_model.get_id_by_title.side_effect = SessionType.get_id_by_title
        
        _recalculate_start_times([meeting])
        
        # Assertions
        print(f"Log 1 Start Time: {log1.Start_Time}") # Should be None
        print(f"Log 2 Start Time: {log2.Start_Time}") # Should be 19:00
        print(f"Log 3 Start Time: {log3.Start_Time}") # Should be None (Hidden)
        print(f"Log 4 Start Time: {log4.Start_Time}") # Should be 19:06 (19:00 + 5 + 1)
        print(f"Log 5 Start Time: {log5.Start_Time}") # Should be None (Type Hidden)
        print(f"Log 6 Start Time: {log6.Start_Time}") # Should be 19:22 (19:06 + 15 + 1)
        
        assert log1.Start_Time is None
        assert log2.Start_Time == time(19, 0)
        assert log3.Start_Time is None
        assert log4.Start_Time == time(19, 6)
        assert log5.Start_Time is None
        assert log6.Start_Time == time(19, 22)
        
        print("\nTest passed!")

if __name__ == "__main__":
    test_recalculate_start_times()
