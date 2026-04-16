import sqlite3
import os

db_path = r"e:\datalogger_project_2102_nosmartlogger\backend\db_manager\data\metadata.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT brand, model FROM inverters LIMIT 10;")
    rows = cursor.fetchall()
    print("Inverters (Brand, Model):")
    for row in rows:
        print(row)
    conn.close()
else:
    print(f"Database not found at {db_path}")
