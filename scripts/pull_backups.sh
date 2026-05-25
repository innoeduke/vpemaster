#!/bin/bash

# VPEMaster Backup Downloader
# Usage: ./scripts/pull_backups.sh

echo "=========================================================="
echo "🔄  VPEMaster Backup Downloader"
echo "=========================================================="

# Dynamically derive the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_USER="ubuntu"
REMOTE_HOST="moleqode.com"
REMOTE_BASE_PATH="/var/www/vpemaster/instance/backup"

echo "📍 Project Root: $PROJECT_ROOT"
echo "🖥️  Remote Host : $REMOTE_USER@$REMOTE_HOST"
echo "=========================================================="

# 1. Checking SSH connection
echo "🔌 Checking SSH connection to $REMOTE_USER@$REMOTE_HOST..."
if ! ssh -q -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" exit; then
    echo "❌ Error: Cannot connect to $REMOTE_USER@$REMOTE_HOST"
    exit 1
fi
echo "✅ SSH connection verified."
echo ""

# Solution B: Add a sleep delay between SSH sessions to prevent Clash/Mihomo/Firewall connection drops
sleep 1.5

# 2. Ensuring local folders exist
echo "📂 Ensuring local folders exist..."
mkdir -p "$PROJECT_ROOT/instance/backup/db"
mkdir -p "$PROJECT_ROOT/instance/backup/system"
mkdir -p "$PROJECT_ROOT/instance/backup/club"
echo "✅ Local directories are ready."
echo ""

# 3. Syncing database backups
echo "🔍 Syncing database backups from remote server..."
rsync -avz --delete -e "ssh -o ConnectTimeout=5" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_PATH/db/" "$PROJECT_ROOT/instance/backup/db/"
echo "✅ Database backups synced."
echo ""

sleep 1.5

# 4. Syncing system resources backups
echo "🔍 Syncing system resources backups from remote server..."
rsync -avz --delete -e "ssh -o ConnectTimeout=5" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_PATH/system/" "$PROJECT_ROOT/instance/backup/system/"
echo "✅ System resources backups synced."
echo ""

sleep 1.5

# 5. Syncing club resources backups
echo "🔍 Syncing club resources backups from remote server..."
rsync -avz --delete -e "ssh -o ConnectTimeout=5" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_PATH/club/" "$PROJECT_ROOT/instance/backup/club/"
echo "✅ Club resources backups synced."
echo ""

# 6. Run post-pull data migrations
echo "🛠️ Running data migrations..."
echo "Running migrate_contact_paths.py..."
python3 "$PROJECT_ROOT/scripts/migrate_contact_paths.py"
echo "Running migrate_owner_meeting_roles.py..."
python3 "$PROJECT_ROOT/scripts/migrate_owner_meeting_roles.py"
echo "✅ Data migrations complete."
echo ""

echo "🎉 Pull complete!"
echo "=========================================================="
