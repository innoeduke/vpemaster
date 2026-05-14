#!/bin/bash
# Run API tests for VPEMaster Getting Started Guide
# Usage: ./run_api_tests.sh
# Note: Only modifies test script, not project code

BASE_URL="http://127.0.0.1:5000"
EMAIL="stephaye"
PASSWORD="Wxm0216!"

echo "======================================"
echo "VPEMaster API Test Suite (Fixed v3)"
echo "Testing Getting Started Guide Tasks"
echo "======================================"
echo ""

# Function to make API calls with form data
test_form() {
    local name="$1"
    local method="$2"
    local url="$3"
    local data="$4"
    
    echo -n "Testing: $name (form)... "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -b cookies.txt -c cookies.txt "${BASE_URL}${url}")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" -b cookies.txt -c cookies.txt -X POST -H "Content-Type: application/x-www-form-urlencoded" -d "$data" "${BASE_URL}${url}")
    fi
    
    if [ "$response" = "200" ] || [ "$response" = "201" ] || [ "$response" = "302" ]; then
        echo "✓ PASS ($response)"
    else
        echo "✗ FAIL ($response)"
    fi
}

# Function to make API calls with JSON
test_json() {
    local name="$1"
    local url="$2"
    local json_data="$3"
    
    echo -n "Testing: $name (json)... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" -b cookies.txt -c cookies.txt -X POST -H "Content-Type: application/json" -d "$json_data" "${BASE_URL}${url}")
    
    if [ "$response" = "200" ] || [ "$response" = "201" ] || [ "$response" = "302" ]; then
        echo "✓ PASS ($response)"
    else
        echo "✗ FAIL ($response)"
    fi
}

# Login first
echo "Step 1: Login"
echo -n "  Logging in as $EMAIL... "
curl -s -o /dev/null -w "%{http_code}" -c cookies.txt -d "username=$EMAIL&password=$PASSWORD" "${BASE_URL}/login"
echo "✓ Done"
echo ""

# Test Initial Settings
echo "=== Initial Settings ==="
test_form "Update club info" "POST" "/about_club/update" "club_name=Test+Club&meeting_schedule=Thursday+7pm"
test_json "Add excomm" "/settings/excomm/add" '{"term":"2026","name":"TestTerm","start_date":"2026-01-01","end_date":"2026-12-31","officers":{}}'
test_form "Add user" "POST" "/user/form" "first_name=Test&last_name=User&email=test@example.com&role=User"
test_form "Add ticket type" "POST" "/settings/tickets/add" "name=TestTicket&category=Technical&priority=Medium"
echo ""

# Test Before Meeting
echo "=== Before the Meeting ==="
test_form "Create meeting" "POST" "/agenda/create" "meeting_date=2026-05-01&start_time=19%3A00&template_file=default"
test_json "Update agenda" "/agenda/update" '{"meeting_id":1,"segments":[]}'
test_json "Book meeting role" "/booking/book" '{"session_id":1,"action":"book","project_id":1,"title":"Test"}'
# speech_log/update needs JSON with media_url or project_id
test_json "Add speech project info" "/speech_log/update/1" '{"project_id":1,"media_url":""}'
echo ""

# Test During Meeting
echo "=== During the Meeting ==="
test_form "View voting" "GET" "/voting" ""
test_json "Cast vote" "/voting/vote" '{"meeting_id":1,"contact_id":1,"award_category":"best_speaker"}'
echo ""

# Test After Meeting
echo "=== After the Meeting ==="
test_form "View voting report" "GET" "/voting" ""
# speech_log/update for video link - needs JSON
test_json "Add video link" "/speech_log/update/1" '{"media_url":"https://youtube.com/watch?v=test"}'
# achievements/record needs user_id (not member_id), achievement_type
test_json "Complete level" "/achievements/record" '{"user_id":1,"achievement_type":"level_complete","level":2,"issue_date":"2026-04-24"}'
echo ""

# Test Club Level Settings
echo "=== Club Level Settings ==="
test_form "Add session type" "POST" "/settings/sessions/add" "name=TestSession&duration=120&description=Test"
test_form "Add custom role" "POST" "/settings/roles/add" "name=CustomRole&default_duration=5&description=Test"
echo ""

# Test User Specific Settings
echo "=== User Specific Settings ==="
test_form "Update contact info" "POST" "/contact/form/1" "name=Updated+Name&email=test@example.com"
test_json "Complete member level" "/achievements/record" '{"user_id":1,"achievement_type":"level_complete","level":3,"issue_date":"2026-04-24"}'
echo ""

# Cleanup
rm -f cookies.txt
echo "======================================"
echo "Test run complete!"
echo "======================================"
