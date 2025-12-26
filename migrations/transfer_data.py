import sys
import os
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def transfer_data():
    app = create_app()
    with app.app_context():
        # Use raw SQL to get data from Users table (ignoring current model definition)
        # Using mappings() to access by name in a robust way
        result = db.session.execute(text("SELECT id, Contact_ID, Member_ID, Mentor_ID, Current_Path, Next_Project, credentials FROM Users"))
        users_data = result.mappings().all()
        
        count = 0
        for row in users_data:
            contact_id = row['Contact_ID']
            if contact_id:
                # Update Contact table
                count += 1
                try:
                    sql = text("""
                        UPDATE Contacts 
                        SET Member_ID=:mid, Mentor_ID=:mentor, Current_Path=:cp, Next_Project=:np, credentials=:cred
                        WHERE id=:cid
                    """)
                    db.session.execute(sql, {
                        "mid": row['Member_ID'],
                        "mentor": row['Mentor_ID'],
                        "cp": row['Current_Path'],
                        "np": row['Next_Project'],
                        "cred": row['credentials'],
                        "cid": contact_id
                    })
                except Exception as e:
                    print(f"Error updating contact {contact_id}: {e}")
        
        db.session.commit()
        print(f"Transferred data for {count} users.")

if __name__ == "__main__":
    transfer_data()
