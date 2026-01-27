#!/bin/bash

# Configuration
BACKUP_FILE="instance/backup/backup_20260125.sql"

echo "----------------------------------------------------------"
echo "🚀 DATABASE RESET AND SETUP STARTED"
echo "----------------------------------------------------------"

# 0. Detect and activate virtual environment
if [ -d "venv" ]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No 'venv' directory found. Proceeding with system python/flask."
fi

# 1. Cleanup all existing data
echo "🧹 Cleaning up existing data..."
flask cleanup-data --force

if [ $? -ne 0 ]; then
    echo "❌ Failed to cleanup data. Aborting."
    exit 1
fi

# 2. Restore metadata (This ensures core records like meeting roles, etc. are present)
echo "🧩 Restoring core metadata..."
flask metadata restore

if [ $? -ne 0 ]; then
    echo "❌ Failed to restore metadata. Aborting."
    exit 1
fi

# 3. Handle migrations (Run any pending upgrades)
echo "🏗️  Running migrations..."
flask db upgrade

if [ $? -ne 0 ]; then
    echo "❌ Failed to run migrations. Aborting."
    exit 1
fi

# 4. Create supporting club
echo "🏢 Creating 'Technical Support' club..."
# Use 000001 as specified by user
flask create-club --club-no "000001" --club-name "Technical Support"

# 5. Create sysadmin user
echo "👤 Creating 'sysadmin' user..."
# Using --club-no as specified by user
flask create-admin --username "sysadmin" --email "admin@vpemaster.com" --password "sysadmin" --contact-name "System Admin" --club-no "000001"

# 6. Create Shanghai Leadership Toastmasters club
echo "🏢 Creating 'Shanghai Leadership Toastmasters'..."
flask create-club --club-no "00868941" --club-name "Shanghai Leadership Toastmasters"

# 7. Import data
echo "📥 Importing data from $BACKUP_FILE..."
flask import-data --file "$BACKUP_FILE" --club-no "00868941"

echo "----------------------------------------------------------"
echo "✅ DATABASE RESET AND SETUP COMPLETE"
echo "----------------------------------------------------------"
