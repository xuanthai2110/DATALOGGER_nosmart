import sqlite3
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import settings

db_path = settings.METADATA_DB

def migrate():
    print(f"Starting migration on {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Tạo bảng server_accounts
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS server_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT UNIQUE,
            password TEXT,
            token TEXT,
            refresh_token TEXT,
            expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
        print("Table 'server_accounts' created or already exists.")

        # 2. Thêm cột server_account_id vào bảng projects nếu chưa có
        cursor.execute("PRAGMA table_info(projects)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'server_account_id' not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN server_account_id INTEGER REFERENCES server_accounts(id)")
            print("Column 'server_account_id' added to 'projects' table.")
        else:
            print("Column 'server_account_id' already exists in 'projects'.")

        # 3. Tạo tài khoản mặc định từ settings hiện tại
        default_username = settings.API_USERNAME
        default_password = settings.API_PASSWORD
        
        if default_username:
            cursor.execute("SELECT id FROM server_accounts WHERE username = ?", (default_username,))
            account = cursor.fetchone()
            
            if not account:
                cursor.execute("""
                    INSERT INTO server_accounts (name, username, password) 
                    VALUES (?, ?, ?)
                """, ("Default Account", default_username, default_password))
                account_id = cursor.lastrowid
                print(f"Created default server account for {default_username}")
            else:
                account_id = account[0]
                print(f"Default server account already exists (ID: {account_id})")

            # 4. Gán tất cả project hiện có vào tài khoản này
            cursor.execute("UPDATE projects SET server_account_id = ? WHERE server_account_id IS NULL", (account_id,))
            print(f"Associated all existing projects with server account ID: {account_id}")

        conn.commit()
        print("Migration completed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
