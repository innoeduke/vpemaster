#!/bin/bash

# 1. Parse arguments
DATABASE_NAME=""
EXPLICIT_FILE=""
BACKUP_PATH=""
USE_INIT=false

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --init)
        USE_INIT=true
        shift # past argument
        ;;
        --path)
        BACKUP_PATH="$2"
        shift # past argument
        shift # past value
        ;;
        -*)
        echo "Unknown option: $1"
        exit 1
        ;;
        *)
        if [ -z "$DATABASE_NAME" ]; then
            DATABASE_NAME="$1"
        elif [ -z "$EXPLICIT_FILE" ]; then
            EXPLICIT_FILE="$1"
        fi
        shift # past argument
        ;;
    esac
done

if [ -z "$DATABASE_NAME" ]; then
    echo "ERROR: database_name is required."
    echo "Usage: $0 <database_name> [backup_file] [--init] [--path <path>]"
    echo "  database_name: Name of the database to restore to (mandatory)"
    echo "  backup_file: Path to backup SQL file (optional)"
    echo "  --init: Force use of 'backup_init.sql' from the backup directory"
    echo "  --path: Specify directory containing backup files"
    exit 1
fi

# 2. Determine backup directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

if [ -n "$BACKUP_PATH" ]; then
    BACKUP_DIR="$BACKUP_PATH"
else
    BACKUP_DIR="$PROJECT_ROOT/instance/backup"
fi

# 3. Determine input file
if [ "$USE_INIT" = true ]; then
    INPUT_FILE="$BACKUP_DIR/backup_${DATABASE_NAME}_init.sql"
    if [ ! -f "$INPUT_FILE" ]; then
         echo "ERROR: --init specified but '$INPUT_FILE' not found."
         exit 1
    fi
    echo "INFO: --init flag used. Restoring from: $INPUT_FILE"
elif [ -n "$EXPLICIT_FILE" ]; then
    INPUT_FILE="$EXPLICIT_FILE"
else
    # Find latest backup
    echo "INFO: No specific backup file provided, searching for latest backup in '$BACKUP_DIR'..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        echo "ERROR: Backup directory '$BACKUP_DIR' does not exist."
        exit 1
    fi

    # Find the latest backup_DBNAME_YYYYMMDD_HHMMSS.sql file
    # Pattern matches: backup_${DATABASE_NAME}_YYYYMMDD_HHMMSS.sql
    # Use quotes around the prefix to handle special chars in DB name, but leave wildcards unquoted
    LATEST_BACKUP=$(ls -1 "$BACKUP_DIR/backup_${DATABASE_NAME}_"[0-9]*_[0-9]*.sql 2>/dev/null | sort -r | head -n 1)
    
    if [ -n "$LATEST_BACKUP" ]; then
        INPUT_FILE="$LATEST_BACKUP"
        echo "INFO: Found latest backup file: $INPUT_FILE"
    else
        # Fallback to default filename logic
        DEFAULT_FILE="$BACKUP_DIR/backup.sql"
        if [ -f "$DEFAULT_FILE" ]; then
            INPUT_FILE="$DEFAULT_FILE"
            echo "INFO: No dated backup found, using default file: $INPUT_FILE"
        else
            echo "ERROR: No backup file found in '$BACKUP_DIR'."
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