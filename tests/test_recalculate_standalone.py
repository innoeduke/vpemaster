
from datetime import time, date, datetime, timedelta

# Mock objects to mimic the database models
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
    def __init__(self, id, Title):
        self.id = id
        self.Title = Title

class Meeting:
    def __init__(self, Meeting_Number, Meeting_Date, Start_Time, club_id=1, ge_mode=0):
        self.Meeting_Number = Meeting_Number
        self.Meeting_Date = Meeting_Date
        self.Start_Time = Start_Time
        self.club_id = club_id
        self.ge_mode = ge_mode

# The function logic copied from app/agenda_routes.py
def standalone_recalculate_start_times(meeting, logs_data):
    current_time = meeting.Start_Time
    
    # logs_data is a list of (log, is_section, is_hidden_type)
    for log, is_section, is_hidden_type in logs_data:
        # Calculate duration first
        duration_val = int(log.Duration_Max or 0)
        
        # Determine if session is hidden (snapshot override or type default)
        is_hidden = log.hidden if log.hidden is not None else is_hidden_type

        # If the session is a section header OR hidden OR its duration is 0,
        # set its time to None and continue (skip time accumulation).
        if is_section or is_hidden or duration_val == 0:
            log.Start_Time = None
            continue

        # The rest of the logic only runs for visible, non-section items.
        log.Start_Time = current_time
        duration_to_add = duration_val
        break_minutes = 1
        
        # Mocking EVAL_ID check
        EVAL_ID = 31
        if log.Type_ID == EVAL_ID and meeting.ge_mode == 1:
            break_minutes += 1
            
        dt_current_time = datetime.combine(meeting.Meeting_Date, current_time)
        next_dt = dt_current_time + timedelta(minutes=duration_to_add + break_minutes)
        current_time = next_dt.time()

def test_recalculate_start_times():
    meeting = Meeting(1, date(2026, 2, 5), time(19, 0))
    
    # Logs
    log1 = SessionLog(1, 1, 1, 0) # Section
    log2 = SessionLog(2, 1, 2, 5) # Normal 5m
    log3 = SessionLog(3, 1, 3, 10, hidden=True) # Hidden override 10m
    log4 = SessionLog(4, 1, 4, 15) # Normal 15m
    log5 = SessionLog(5, 1, 5, 20) # Type hidden 20m
    log6 = SessionLog(6, 1, 6, 25) # Normal 25m
    
    # Input data: (log, is_section, is_hidden_type)
    logs_data = [
        (log1, True, False),
        (log2, False, False),
        (log3, False, False),
        (log4, False, False),
        (log5, False, True),
        (log6, False, False),
    ]
    
    standalone_recalculate_start_times(meeting, logs_data)
    
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
    
    print("\nStandalone test passed!")

if __name__ == "__main__":
    test_recalculate_start_times()
