import os
import pymysql
import re
from dotenv import load_dotenv

load_dotenv()

def debug_excomm():
    db_url = os.getenv("DATABASE_URL")
    match = re.match(r"mysql\+pymysql://([^:]+):([^@]+)@([^/]+)/(.+)", db_url)
    user, password, host, db_name = match.groups()
    
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # Get latest ExComm for club 1 (assuming meeting 959 is club 1)
            cursor.execute("SELECT club_id FROM Meetings WHERE Meeting_Number = 959")
            club_id = cursor.fetchone()['club_id']
            print(f"Club ID for 959: {club_id}")
            
            cursor.execute("SELECT * FROM excomm WHERE club_id = %s ORDER BY id DESC LIMIT 1", (club_id,))
            excomm = cursor.fetchone()
            print(f"ExComm row: {excomm}")
            
            if excomm:
                vpm_id = excomm.get('vpm_id')
                print(f"VPM ID: {vpm_id}")
                if vpm_id:
                    cursor.execute("SELECT Name FROM Contacts WHERE id = %s", (vpm_id,))
                    contact = cursor.fetchone()
                    print(f"VPM Contact: {contact}")
    finally:
        conn.close()

if __name__ == "__main__":
    debug_excomm()
