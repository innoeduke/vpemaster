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
mkdir -p "$PROJECT_ROOT/instance/backup/resources"
echo "✅ Local directories are ready."
echo ""

# 3. Querying remote server for database backup
echo "🔍 Querying remote server for the newest database backup..."
LATEST_DB=$(ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "ls -t $REMOTE_BASE_PATH/db/backup_*.sql 2>/dev/null | head -n 1")

if [ -z "$LATEST_DB" ]; then
    echo "⚠️  No backup files found in remote directory: $REMOTE_BASE_PATH/db"
else
    DB_FILENAME=$(basename "$LATEST_DB")
    echo "📦 Found newest remote database: $DB_FILENAME"
    echo "⬇️  Downloading database backup..."
    scp -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST:$LATEST_DB" "$PROJECT_ROOT/instance/backup/db/"
    echo "✅ Database backup downloaded successfully to $PROJECT_ROOT/instance/backup/db/$DB_FILENAME"
fi
echo ""

# Solution B: Add a sleep delay between SSH sessions to prevent Clash/Mihomo/Firewall connection drops
sleep 1.5

# 4. Querying remote server for resources backup
echo "🔍 Querying remote server for the newest resources backup..."
LATEST_RES=$(ssh -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST" "ls -t $REMOTE_BASE_PATH/resources/resources_*.zip 2>/dev/null | head -n 1")

if [ -z "$LATEST_RES" ]; then
    echo "⚠️  No backup files found in remote directory: $REMOTE_BASE_PATH/resources"
else
    RES_FILENAME=$(basename "$LATEST_RES")
    echo "📦 Found newest remote resources: $RES_FILENAME"
    echo "⬇️  Downloading resources backup..."
    scp -o ConnectTimeout=5 "$REMOTE_USER@$REMOTE_HOST:$LATEST_RES" "$PROJECT_ROOT/instance/backup/resources/"
    echo "✅ Resources backup downloaded successfully to $PROJECT_ROOT/instance/backup/resources/$RES_FILENAME"
fi
echo ""

echo "🎉 Pull complete!"
echo "=========================================================="
