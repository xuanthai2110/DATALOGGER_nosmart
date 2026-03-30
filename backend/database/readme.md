🔹 Project
post_project(data)
post_project_with_id(data, server_id)
get_project(project_id)
get_project_first()
get_projects() / get_all_projects()
upsert_project(data, project_id=None)
patch_project(project_id, data)
update_project_sync(project_id, ...)
delete_project(project_id)
🔹 Inverter
post_inverter(data)
post_inverter_with_id(data, server_id)
upsert_inverter(data)
get_inverter_id(inverter_id)
get_inverter_by_serial(serial)
get_inverters_by_project(project_id)
get_inverter()
patch_inverter(inverter_id, data)
update_inverter_sync(inverter_id, ...)
delete_inverter(inverter_id)
mark_inverter_inactive(inverter_id, replaced_by_id)
🔹 Comm Config
get_comm()
get_comm_id(config_id)
post_comm(config)
patch_comm(config_id, data)
delete_comm(config_id)
reset_comm()
upsert_comm(config)
🔹 User
post_user(user, hashed_password)
get_user_name(username)
get_users()
🟦 2. RealtimeDB (realtime.db)
🔹 Project realtime
post_project_realtime(data)
get_latest_project_realtime(project_id)
get_project_realtime_range(project_id, start, end)
delete_project_realtime_before(time)
🔹 Inverter AC realtime
post_inverter_ac_batch(records)
get_inverter_ac_range(inverter_id, start, end)
get_latest_inverter_ac_realtime(inverter_id)
🔹 MPPT
post_mppt(data)
post_mppt_batch(records)
get_latest_mppt_batch(inverter_id)
🔹 String
post_string_batch(records)
get_latest_string_batch(inverter_id)
🔹 Error
post_inverter_error(data)
get_inverter_errors(inverter_id, start=None, end=None)
delete_errors_before(time)
🔹 Cleanup
delete_before(time)
delete_inverter_data(inverter_id)
🔹 Latest realtime (JSON cache trong DB)
upsert_latest_realtime(inverter_id, project_id, data)
🔹 Outbox (gửi lên server)
post_to_outbox(project_id, data)
get_all_outbox()
delete_from_outbox(record_id)
🟦 3. CacheDB (RAM DB)
upsert_latest_realtime(inverter_id, project_id, data)
get_latest_realtime(inverter_id)

👉 dùng cho:

Web UI local
tránh ghi SD card
🟩 4. ProjectService (service layer)
🔹 Project
create_project(data)
get_project(project_id)
get_all_projects()
update_project(project_id, data)
delete_project(project_id)
🔹 Inverter
create_inverter(data)
get_inverter_id(inverter_id)
delete_inverter(inverter_id)
🔹 Realtime
add_project_realtime_data(data)
get_latest_project_data(project_id)
🔥 🔹 Snapshot (QUAN TRỌNG NHẤT)
get_project_snapshot(project_id)

👉 trả về:

{
  "project": {...},
  "metadata": {...},
  "inverters": [...]
}

👉 dùng cho:

dashboard
API frontend
SCADA view
🔹 Cleanup
cleanup_old_data(before_timestamp)
🔥 5. Gợi ý cách dùng nhanh (thực tế)
👉 Lấy dashboard (quan trọng nhất)
service.get_project_snapshot(project_id=1)
👉 Lấy danh sách inverter
db.get_inverters_by_project(project_id=1)
👉 Lấy realtime inverter
rt_db.get_latest_inverter_ac_realtime(inverter_id=1)
👉 Ghi dữ liệu realtime
rt_db.post_inverter_ac_batch(records)
👉 Cleanup dữ liệu cũ
service.cleanup_old_data("2026-01-01T00:00:00")