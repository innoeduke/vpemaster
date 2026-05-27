#!/bin/bash

# setup_cron_backups.sh
# Sets up cron jobs for VPEMaster backups.
# - Full backup (DB + Files) every Wednesday at 10:00 PM
# - DB-only backup the other days at 10:00 PM (DB backups are always full dumps)

set -e

# --- Configuration ---
# Resolve the true directory of this script regardless of where it's executed from
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

if [ ! -d "$PROJECT_ROOT/venv" ]; then
    # Fallback to typical production path if not run from project structure
    PROJECT_ROOT="/var/www/vpemaster"
fi

FLASK_CMD="$PROJECT_ROOT/venv/bin/flask"
CRON_LOG="$PROJECT_ROOT/logs/backup_cron.log"

# OS Detection and User Configuration
OS_TYPE="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="macos"
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" == "ubuntu" || "$ID" == "opencloudos" ]]; then
        OS_TYPE="linux"
    fi
fi

# Determine which user should run the backup
if [ "$OS_TYPE" == "macos" ]; then
    RUN_AS_USER=$(whoami)
else
    RUN_AS_USER="ubuntu"
fi

# Ensure logs directory exists and has correct permissions
mkdir -p "$PROJECT_ROOT/logs"
if [ "$EUID" -eq 0 ] && [ "$OS_TYPE" == "linux" ]; then
    chown "$RUN_AS_USER" "$PROJECT_ROOT/logs"
fi

echo "🚀 Setting up backup cron jobs for VPEMaster..."
echo "Project Root: $PROJECT_ROOT"
echo "Run as User: $RUN_AS_USER"

# Define common PATH to ensure cron can find binaries like mysqldump
CRON_PATH="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/homebrew/bin"

if [ "$OS_TYPE" == "linux" ]; then
    # On Linux, use /etc/cron.d/ for a clean system-wide cron job specifying the user
    CRON_FILE="/etc/cron.d/vpemaster_backups"
    
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  Please run this script with sudo to install system-wide cron jobs in /etc/cron.d/"
        exit 1
    fi

    cat << EOF > "$CRON_FILE"
# VPEMaster Backups
$CRON_PATH

# Full backup (DB + Files) every Wednesday at 10:00 PM
0 22 * * 3 $RUN_AS_USER cd "$PROJECT_ROOT" && FLASK_APP=run.py "$FLASK_CMD" resources all backup --full >> "$CRON_LOG" 2>&1

# DB-only backup the other days at 10:00 PM
0 22 * * 0-2,4-6 $RUN_AS_USER cd "$PROJECT_ROOT" && FLASK_APP=run.py "$FLASK_CMD" resources db backup >> "$CRON_LOG" 2>&1
EOF

    chmod 644 "$CRON_FILE"
    echo "✅ System cron jobs installed successfully to $CRON_FILE"
    cat "$CRON_FILE"

else
    # On macOS, fallback to standard crontab
    CRON_FULL="0 22 * * 3 cd \"$PROJECT_ROOT\" && FLASK_APP=run.py \"$FLASK_CMD\" resources all backup --full >> \"$CRON_LOG\" 2>&1"
    CRON_DB_ONLY="0 22 * * 0-2,4-6 cd \"$PROJECT_ROOT\" && FLASK_APP=run.py \"$FLASK_CMD\" resources db backup >> \"$CRON_LOG\" 2>&1"

    TMP_CRON=$(mktemp)
    crontab -l > "$TMP_CRON" 2>/dev/null || true

    # Remove any existing vpemaster backup cron jobs
    sed -i '' '/vpemaster.*backup/d' "$TMP_CRON"
    # Also clean up the previous PATH entry if we added it, but let's just append to the file safely
    sed -i '' '/# VPEMaster Backups/d' "$TMP_CRON"
    sed -i '' '/PATH=.*vpemaster/d' "$TMP_CRON" 

    # Append new cron jobs
    echo "" >> "$TMP_CRON"
    echo "# VPEMaster Backups" >> "$TMP_CRON"
    # Cron executes via restricted PATH, ensure it has necessary paths for mysqldump etc.
    echo "$CRON_FULL" >> "$TMP_CRON"
    echo "$CRON_DB_ONLY" >> "$TMP_CRON"

    crontab "$TMP_CRON"
    rm "$TMP_CRON"
    
    echo "✅ Cron jobs installed successfully."
    echo "Current VPEMaster crontab entries:"
    crontab -l | grep -A 2 "VPEMaster Backups"
fi
