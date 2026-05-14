#!/bin/bash

# Sync Backups to Remote Server
# Usage: ./scripts/sync_backups.sh

REMOTE_USER="vpemaster_user"
REMOTE_HOST="moleqode.com"
REMOTE_BASE_PATH="/var/www/vpemaster/instance/backup"

# Local paths
LOCAL_DB_DIR="instance/backup/db"
LOCAL_RES_DIR="instance/backup/resources"

# Find latest files
LATEST_DB=$(ls -t "$LOCAL_DB_DIR"/backup_*.sql 2>/dev/null | head -n 1)
LATEST_RES=$(ls -t "$LOCAL_RES_DIR"/resources_*.zip 2>/dev/null | head -n 1)

if [ -z "$LATEST_DB" ] && [ -z "$LATEST_RES" ]; then
    echo "❌ Error: No backups found in $LOCAL_DB_DIR or $LOCAL_RES_DIR."
    echo "Run 'flask backup create' first."
    exit 1
fi

# Ensure remote directories exist
echo "📂 Ensuring remote directories exist..."
ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_BASE_PATH/db $REMOTE_BASE_PATH/resources"

if [ -n "$LATEST_DB" ]; then
    echo "📦 Syncing latest DB: $(basename "$LATEST_DB")"
    scp "$LATEST_DB" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_PATH/db/"
fi

if [ -n "$LATEST_RES" ]; then
    echo "📦 Syncing latest Resources: $(basename "$LATEST_RES")"
    scp "$LATEST_RES" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_PATH/resources/"
fi

echo "✅ Sync complete."
