# VPEMaster API Guide Tests

Tests all tasks from the Getting Started Guide using the VPEMaster API.

## Credentials

- **Username:** stephaye
- **Password:** Wxm0216!

## Running Tests

### Option 1: Shell Script (Quick)
```bash
cd ~/workspaces/vpemaster
./tests/api_guide/run_api_tests.sh
```

### Option 2: Pytest (Detailed)
```bash
cd ~/workspaces/vpemaster
pytest tests/api_guide/test_getting_started_guide.py -v
```

## Test Coverage

### Initial Settings
- [x] Update club info (`POST /about_club/update`)
- [x] Add excomm team (`POST /settings/excomm/add`)
- [x] Add club members (`POST /user/form`)
- [x] Add ticket types (`POST /settings/tickets/add`)

### Before the Meeting
- [x] Create meeting (`POST /agenda/create`)
- [x] Update sessions (`POST /agenda/update`)
- [x] Book meeting roles (`POST /booking/book`)
- [x] Add project info (`POST /speech_log/update/<id>`)
- [x] Generate slides (`GET /agenda/ppt/<id>`)

### During the Meeting
- [x] Add roster entries (`POST /api/entry`)
- [x] Add table topics speakers (`POST /agenda/update`)
- [x] Start voting (`POST /voting`)
- [x] Cast votes (`POST /voting/vote`)

### After the Meeting
- [x] View voting reports (`GET /voting`)
- [x] Add video links (`POST /speech_log/update/<id>`)
- [x] Complete levels (`POST /achievements/record`)

### Club Level Settings
- [x] Add session types (`POST /settings/sessions/add`)
- [x] Add custom roles (`POST /settings/roles/add`)

### User Specific Settings
- [x] Update contact info (`POST /contact/form/<id>`)
- [x] Complete levels (`POST /achievements/record`)

## Notes

- Tests assume VPEMaster is running on `http://localhost:5000`
- Some tests may fail if required data (clubs, members) doesn't exist
- Check server logs for detailed error messages
