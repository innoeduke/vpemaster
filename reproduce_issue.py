import sys
import os

sys.path.append(os.path.abspath(os.getcwd()))

try:
    import app
    print(f"Imported app: {app}")
    print(f"app type: {type(app)}")
    print(f"app file: {app.__file__}")
except Exception as e:
    print(f"Failed to import app: {e}")

try:
    from app import create_app
    print(f"Imported create_app: {create_app}")
except Exception as e:
    print(f"Failed to import create_app: {e}")

try:
    from app import speech_logs_routes
    print(f"Imported speech_logs_routes: {speech_logs_routes}")
except Exception as e:
    print(f"Failed to import speech_logs_routes: {e}")

try:
    from app.speech_logs_routes import _calculate_completion_summary
    print(f"Imported _calculate_completion_summary: {_calculate_completion_summary}")
except Exception as e:
    print(f"Failed to import _calculate_completion_summary: {e}")
