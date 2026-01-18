#!/bin/bash

# Database Backup Script
# Usage: ./scripts/backup_db.sh <database_name>

# Check if database name is provided
if [ -z "$1" ]; then
    echo "Error: Database name is required."
    echo "Usage: $0 <database_name>"
    exit 1
fi

DB_NAME=$1
BACKUP_DIR="instance/backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/backup_${DB_NAME}_${TIMESTAMP}.sql"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Extract credentials from .env
# Assuming DATABASE_URL format: mysql+pymysql://user:password@host/dbname
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found."
    exit 1
fi

DATABASE_URL=$(grep "DATABASE_URL" "$ENV_FILE" | cut -d '=' -f2-)

# Simple extraction for demo purposes. 
# Robust parsing might be better but this works for the known format.
USER=$(echo "$DATABASE_URL" | sed -e 's|mysql+pymysql://||' -e 's|:.*||')
PASS=$(echo "$DATABASE_URL" | sed -e 's|.*://[^:]*:||' -e 's|@.*||')
HOST=$(echo "$DATABASE_URL" | sed -e 's|.*@||' -e 's|/.*||')

# Perform backup
echo "Backing up database: $DB_NAME to $BACKUP_FILE..."
echo "Ignoring table: alembic_version"
echo "Note: Using --no-defaults to avoid conflicts with global config (e.g., ~/.my.cnf)"

# Use --no-defaults to prevent reading incompatible variables from ~/.my.cnf
# Use --no-tablespaces to avoid PROCESS privilege requirement
# Use --set-gtid-purged=OFF to avoid GTID related warnings
# Use --single-transaction for a consistent backup without locking tables
mysqldump --no-defaults -h "$HOST" -u "$USER" -p"$PASS" \
    --no-tablespaces \
    --set-gtid-purged=OFF \
    --single-transaction \
    --ignore-table="${DB_NAME}.alembic_version" \
    "$DB_NAME" > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "Backup successful: $BACKUP_FILE"
else
    echo "Error: Backup failed."
    exit 1
fi
