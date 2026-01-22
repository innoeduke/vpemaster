
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_meeting_data(meeting_num):
    db_url = os.getenv("DATABASE_URL")
    # mysql+pymysql://root:hondaGL9565!@127.0.0.1/vpemaster
    db_info = db_url.split("://")[1]
    user_pass, host_db = db_info.split("@")
    user, password = user_pass.split(":")
    host, db_name = host_db.split("/")
    
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=db_name,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            # 1. Get Meeting and Club info
            sql = """
            SELECT m.Meeting_Date, m.Meeting_Number, c.club_name 
            FROM Meetings m
            JOIN clubs c ON m.club_id = c.id
            WHERE m.Meeting_Number = %s
            """
            cursor.execute(sql, (meeting_num,))
            meeting = cursor.fetchone()
            print("Meeting:", meeting)
            
            # 2. Get Session Logs (Roles)
            sql = """
            SELECT 
                sl.id, 
                sl.Meeting_Seq, 
                st.Title as Session_Type, 
                mr.name as Role_Name, 
                con.Name as Owner_Name,
                sl.credentials,
                sl.Session_Title,
                p.Project_Name,
                sl.project_code
            FROM Session_Logs sl
            JOIN Session_Types st ON sl.Type_ID = st.id
            LEFT JOIN meeting_roles mr ON st.role_id = mr.id
            LEFT JOIN Contacts con ON sl.Owner_ID = con.id
            LEFT JOIN Projects p ON sl.Project_ID = p.id
            WHERE sl.Meeting_Number = %s
            ORDER BY sl.Meeting_Seq
            """
            cursor.execute(sql, (meeting_num,))
            logs = cursor.fetchall()
            for l in logs:
                print(l)
                
    finally:
        conn.close()

if __name__ == "__main__":
    get_meeting_data(959)
