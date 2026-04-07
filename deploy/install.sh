#!/bin/bash
# install.sh
# Kịch bản tự động cài đặt Datalogger Service trên Raspberry Pi / Linux

set -e

echo "==========================================="
echo " Cài đặt Datalogger Systemd Service"
echo "==========================================="

# Biến nhận diện thư mục hiện tại và tên file service
SERVICE_NAME="datalogger.service"
CURRENT_DIR=$(pwd)
SERVICE_DIR="/etc/systemd/system"

# 1. Xác minh file service có tồn tại không
if [ ! -f "deploy/${SERVICE_NAME}" ]; then
    echo "[LỖI] Không tìm thấy file deploy/${SERVICE_NAME}! Hãy chạy lệnh này ở thư mục gốc của dự án."
    exit 1
fi

# 2. Thay thế path thực tế của hệ thống vào WorkingDirectory của file service tạm
echo "[INFO] Đang cấu hình đường dẫn thư mục..."
sed "s|WorkingDirectory=.*|WorkingDirectory=${CURRENT_DIR}|g" "deploy/${SERVICE_NAME}" > /tmp/${SERVICE_NAME}

# 3. Copy file vào /etc/systemd/system
echo "[INFO] Copy file service vào ${SERVICE_DIR} (Yêu cầu sudo)..."
sudo cp /tmp/${SERVICE_NAME} ${SERVICE_DIR}/${SERVICE_NAME}

# 4. Kích hoạt và dọn dẹp
echo "[INFO] Cập nhật daemon và kích hoạt khởi động tự động..."
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}

echo "==========================================="
echo " Cài đặt hoàn tất!"
echo " Lệnh khả dụng:"
echo "   Khởi động: sudo systemctl start ${SERVICE_NAME}"
echo "   Kiểm tra:  sudo systemctl status ${SERVICE_NAME}"
echo "   Dừng lại:  sudo systemctl stop ${SERVICE_NAME}"
echo "==========================================="
