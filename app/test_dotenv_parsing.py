
import os
import sys
from dotenv import dotenv_values

# Simulate the logic in tally_sync.py
basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
env_path = os.path.join(basedir, '.env_test_repro')

print(f"Looking for .env at: {env_path}")

if os.path.exists(env_path):
    config = dotenv_values(env_path)
    print(f"Loaded config keys: {list(config.keys())}")
    print(f"TALLY_API_KEY: {config.get('TALLY_API_KEY')}")
    print(f"TALLY_FORM_ID: {config.get('TALLY_FORM_ID')}")
else:
    print(".env file not found")
