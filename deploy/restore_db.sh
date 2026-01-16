#!/bin/bash

# 1. Check input parameters - database_name is mandatory
if [ -z "$1" ]; then
    echo "ERROR: database_name is required."
    echo "Usage: $0 <database_name> [backup_file]"
    echo "  database_name: Name of the database to restore to (mandatory)"
    echo "  backup_file: Path to backup SQL file (optional, defaults to latest backup)"
    exit 1
fi

DATABASE_NAME="$1"

# 2. Determine backup file to use
if [ -n "$2" ]; then
    # If second parameter provided, use it as the backup file
    INPUT_FILE="$2"
else
    # If no backup file specified, find the latest backup from instance/backup directory
    # Get the directory where this script is located
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    # Navigate to project root (one level up from tests directory)
    PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
    BACKUP_DIR="$PROJECT_ROOT/instance/backup"
    
    echo "INFO: No backup file provided, searching for latest backup in '$BACKUP_DIR' (format: backup_YYYYMMDD.sql)..."
    
    # Find the latest backup_YYYYMMDD.sql file
    # Use sort -r to reverse sort filenames, take the first one as the latest date
    LATEST_BACKUP=$(ls -1 $BACKUP_DIR/backup_[0-9]*.sql 2>/dev/null | sort -r | head -n 1)
    
    if [ -n "$LATEST_BACKUP" ]; then
        INPUT_FILE="$LATEST_BACKUP"
        echo "INFO: Found latest backup file: $INPUT_FILE"
    else
        # Fallback to default filename logic
        DEFAULT_FILE="backup.sql"
        if [ -f "$DEFAULT_FILE" ]; then
            INPUT_FILE="$DEFAULT_FILE"
            echo "INFO: No dated backup found, using default file: $INPUT_FILE"
        else
            echo "ERROR: No backup file found."
            exit 1
        fi
    fi
fi

# 3. Check for MySQL config file
MYSQL_CONFIG="$HOME/.my.cnf"
if [ -f "$MYSQL_CONFIG" ]; then
    echo "INFO: Found MySQL config file: $MYSQL_CONFIG"
    MYSQL_CMD="mysql --defaults-file=$MYSQL_CONFIG"
else
    echo "INFO: MySQL config file not found, will prompt for password"
    MYSQL_CMD="mysql -u root -p"
fi

# 4. Execute import command
echo "INFO: Importing data from '$INPUT_FILE' to database '$DATABASE_NAME'..."
$MYSQL_CMD "$DATABASE_NAME" < "$INPUT_FILE"

# 5. Check if command executed successfully
if [ $? -eq 0 ]; then
    echo "INFO: Import successful!"
else
    echo "ERROR: Import failed. Please check the SQL file or database permissions."
fi