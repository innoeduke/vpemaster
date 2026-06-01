#!/bin/bash

# Configuration
BACKUP_FILE="instance/backup/backup_20260128.sql"

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
# Note: cleanup-data also resets autoincrement sequences to ensured fresh IDs
flask cleanup-data --force

if [ $? -ne 0 ]; then
    echo "❌ Failed to cleanup data. Aborting."
    exit 1
fi

# 2. Handle migrations (Run any pending upgrades to ensure schema exists)
echo "🏗️  Running migrations..."
flask db upgrade

if [ $? -ne 0 ]; then
    echo "❌ Failed to run migrations. Aborting."
    exit 1
fi

# 3. Create supporting club (Required for Global Metadata)
echo "🏢 Creating 'Technical Support' club (Club 1)..."
# Use 000001 as specified by user. This MUST be the first club to get ID=1.
# Use --skip-seed to avoid creating default roles that conflict with metadata restore
flask create-club --club-no "000001" --club-name "Technical Support" --skip-seed

if [ $? -ne 0 ]; then
    echo "❌ Failed to create Technical Support club. Aborting."
    exit 1
fi

# 4. Restore metadata (Depends on Club 1 existing)
if [ -f "instance/metadata_dump.json" ]; then
    echo "🧩 Restoring core metadata from instance/metadata_dump.json..."
    flask metadata restore --file "instance/metadata_dump.json"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to restore metadata. Aborting."
        exit 1
    fi
else
    echo "⚠️  No metadata dump found at instance/metadata_dump.json. Skipping metadata restore."
fi

# 5. Create sysadmin user
echo "👤 Creating 'sysadmin' user..."
# Using --club-no as specified by user
flask create-admin --username "sysadmin" --email "admin@vpemaster.com" --password "sysadmin" --contact-name "System Admin" --club-no "000001"

# 6. Create Shanghai Leadership Toastmasters club
echo "🏢 Creating 'Shanghai Leadership Toastmasters'..."
flask create-club --club-no "00868941" --club-name "Shanghai Leadership Toastmasters Club" --skip-seed

# 7. Import data
echo "📥 Importing data from $BACKUP_FILE..."
flask import-data --file "$BACKUP_FILE" --club-no "00868941"

echo "----------------------------------------------------------"
echo "✅ DATABASE RESET AND SETUP COMPLETE"
echo "----------------------------------------------------------"
