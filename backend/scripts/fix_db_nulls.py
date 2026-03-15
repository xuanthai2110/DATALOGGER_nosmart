import sqlite3
import os

db_path = r'e:\datalogger_project_2102\code\database\metadata.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
    exit(1)

conn = sqlite3.connect(db_path)
try:
    c = conn.cursor()
    # Fix projects
    c.execute("UPDATE projects SET server_id = NULL WHERE server_id IN ('NULL', 'Null', 'None')")
    c.execute("UPDATE projects SET server_request_id = NULL WHERE server_request_id IN ('NULL', 'Null', 'None')")
    
    # Fix inverters
    c.execute("UPDATE inverters SET server_id = NULL WHERE server_id IN ('NULL', 'Null', 'None')")
    c.execute("UPDATE inverters SET server_request_id = NULL WHERE server_request_id IN ('NULL', 'Null', 'None')")
    
    conn.commit()
    print("Successfully cleaned up pseudo-NULL strings from database.")
except Exception as e:
    print(f"Error during cleanup: {e}")
finally:
    conn.close()
