#!/usr/bin/env python3
"""Check foreign key constraint names in the database."""

from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Query for user_clubs foreign keys
    result = db.session.execute(text("""
        SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME 
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'user_clubs' 
        AND REFERENCED_TABLE_NAME IS NOT NULL
    """))
    
    print("user_clubs foreign key constraints:")
    for row in result:
        print(f"  {row[0]}: {row[1]} -> {row[2]}")
    
    # Query for permission_audits foreign keys
    result = db.session.execute(text("""
        SELECT CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME 
        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'permission_audits' 
        AND REFERENCED_TABLE_NAME IS NOT NULL
    """))
    
    print("\npermission_audits foreign key constraints:")
    for row in result:
        print(f"  {row[0]}: {row[1]} -> {row[2]}")
