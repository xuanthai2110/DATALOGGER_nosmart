# Hướng dẫn Triển khai Raspberry Pi (Deployment Guide for RPi)

Tài liệu này hướng dẫn cách lấy mã nguồn từ GitHub, cài đặt môi trường và chạy các dịch vụ trên Raspberry Pi.

---

## 1. Lấy mã nguồn từ GitHub

Mở Terminal trên Raspberry Pi và chạy các lệnh sau:

```bash
# Di chuyển vào thư mục bạn muốn đặt dự án
cd ~

# Clone dự án từ GitHub (Thay <URL_CUA_BAN> bằng link repo github)
git clone <URL_CUA_BAN>

# Truy cập vào thư mục dự án
cd datalogger_project_2102
```

## 2. Cài đặt Môi trường Python

Chúng ta sẽ sử dụng môi trường ảo (venv) để tránh xung đột thư viện hệ thống:

```bash
# Cài đặt python3-venv nếu chưa có
sudo apt update
sudo apt install python3-venv python3-pip -y

# Tạo môi trường ảo
python3 -m venv venv

# Kích hoạt môi trường ảo
source venv/bin/activate

# Cài đặt các thư viện cần thiết
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## 3. Chạy các Dịch vụ (Services)

Bạn nên chạy các dịch vụ này trong các session `screen` hoặc `tmux` để chúng vẫn chạy sau khi bạn tắt Terminal.

### A. Dịch vụ Đọc dữ liệu (Polling Service)
Đây là dịch vụ chính để đọc dữ liệu từ Inverter mỗi 10 giây và gửi lên Server.

```bash
# Kích hoạt venv (nếu chưa kích hoạt)
source venv/bin/activate

# Chạy script polling
python3 backend/scripts/run_polling.py
```

### B. Dịch vụ Web UI Local (Local Dashboard)
Dịch vụ này cung cấp giao diện web tại địa chỉ `http://<IP_RASPBERRY_PI>:5000`.

```bash
# Kích hoạt venv
source venv/bin/activate

# Chạy script web
python3 backend/scripts/run_web.py
```

## 4. Tự động khởi chạy cùng hệ thống (Systemd)

Để các dịch vụ tự khởi động khi Raspberry Pi bật nguồn, bạn nên tạo các file service trong `/etc/systemd/system/`.

**Ví dụ cho polling.service:**
```bash
[Unit]
Description=Solar Datalogger Polling Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/datalogger_project_2102
ExecStart=/home/pi/datalogger_project_2102/venv/bin/python3 backend/scripts/run_polling.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---
*Lưu ý: Luôn đảm bảo Inverter đã được bật và kết nối vật lý với Raspberry Pi (RS485 hoặc Ethernet).*
