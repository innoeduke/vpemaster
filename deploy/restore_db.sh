#!/bin/bash

# 1. Parse arguments
DATABASE_NAME=""
EXPLICIT_FILE=""
BACKUP_PATH=""
USE_INIT=false

# Determine directory locations early
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

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

# If DATABASE_NAME is not provided, try to find it in .env
if [ -z "$DATABASE_NAME" ]; then
    ENV_FILE="$PROJECT_ROOT/.env"
    if [ -f "$ENV_FILE" ]; then
        DATABASE_URL=$(grep "DATABASE_URL" "$ENV_FILE" | cut -d '=' -f2-)
        # Extract DB name: remove everything up to the last slash, then remove query params
        EXTRACTED_DB=$(echo "$DATABASE_URL" | sed -e 's|.*/||' -e 's|?.*||')
        if [ -n "$EXTRACTED_DB" ]; then
            DATABASE_NAME="$EXTRACTED_DB"
            echo "INFO: database_name not provided. Using '$DATABASE_NAME' from .env"
        fi
    fi
fi

# If still not found, try getting it from ~/.my.cnf
if [ -z "$DATABASE_NAME" ]; then
    MY_CNF="$HOME/.my.cnf"
    if [ -f "$MY_CNF" ]; then
        # Look for 'database = name' or 'database=name'
        # Normalize spaces around '=', grab right side
        EXTRACTED_DB=$(grep -E "^database\s*=" "$MY_CNF" | head -n 1 | sed -e 's/database\s*=\s*//' -e 's/^\s*//' -e 's/\s*$//')
        if [ -n "$EXTRACTED_DB" ]; then
            DATABASE_NAME="$EXTRACTED_DB"
            echo "INFO: database_name not provided. Using '$DATABASE_NAME' from $MY_CNF"
        fi
    fi
fi

if [ -z "$DATABASE_NAME" ] && [ "$USE_INIT" = false ]; then
    # Relaxed check: if --init is used, we might not strictly need DB name IF the script didn't rely on it for file searching.
    # BUT, the script currently searches for backup_${DATABASE_NAME}_... unless --init is used.
    # However, user said "no need to provide db name when --init is used".
    # And currently INPUT_FILE for --init is hardcoded to backup_init.sql.
    # So if --init is used, we can proceed without DATABASE_NAME for the *file finding* part,
    # BUT we still need a database name to *restore into* (mysql $DATABASE_NAME < ...).
    # So DATABASE_NAME is still mandatory for the actual restore command.
    echo "ERROR: database_name is required and could not be found in .env or ~/.my.cnf."
    echo "Usage: $0 [database_name] [backup_file] [--init] [--path <path>]"
    exit 1
fi


if [ -n "$BACKUP_PATH" ]; then
    BACKUP_DIR="$BACKUP_PATH"
else
    BACKUP_DIR="$PROJECT_ROOT/instance/backup"
fi

# 3. Determine input file
if [ "$USE_INIT" = true ]; then
    INPUT_FILE="$BACKUP_DIR/backup_init.sql"
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