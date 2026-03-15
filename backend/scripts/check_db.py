
import sqlite3
import os

db_path = "database/metadata.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, name FROM projects;").fetchall()
    print("Projects in DB:")
    for r in rows:
        print(f"ID: {r['id']}, Name: {r['name']}")
    conn.close()
else:
    print(f"DB not found: {db_path}")
