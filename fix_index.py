import sqlite3
import os

# Đường dẫn tới DB
db_path = r"e:\datalogger_project_2102_nosmartlogger\backend\db_manager\data\metadata.db"

if not os.path.exists(db_path):
    print(f"Không tìm thấy file DB: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Lấy tất cả project_id
cursor.execute("SELECT DISTINCT project_id FROM inverters")
projects = cursor.fetchall()

total_updated = 0

for (project_id,) in projects:
    if project_id is None:
        continue
        
    print(f"\nĐang xử lý Project ID: {project_id}")
    
    # Lấy danh sách inverter của project này, sắp xếp theo ID (hoặc thứ tự hiện tại)
    cursor.execute("SELECT id, serial_number, inverter_index FROM inverters WHERE project_id = ? ORDER BY id ASC", (project_id,))
    inverters = cursor.fetchall()
    
    new_index = 1
    for inv_id, serial, old_index in inverters:
        if old_index != new_index:
            cursor.execute("UPDATE inverters SET inverter_index = ? WHERE id = ?", (new_index, inv_id))
            print(f"  - Đã cập nhật Inverter {serial} (ID: {inv_id}): Index {old_index} -> {new_index}")
            total_updated += 1
        else:
            print(f"  - Inverter {serial} (ID: {inv_id}): Index đã chuẩn ({old_index}), bỏ qua.")
            
        new_index += 1

conn.commit()
conn.close()

print(f"\nĐã hoàn thành! Tổng số inverter được fix index: {total_updated}")
