"""
backend/api/network_api.py — API cấu hình mạng LAN (eth0) và WLAN (wlan0) cho Raspberry Pi 3B+
"""
from fastapi import APIRouter, Depends, Body, HTTPException
from backend.db_manager import MetadataDB
from backend.api.auth_api import get_current_user_id
from backend.core import settings as app_config
import logging
import subprocess
import threading
import time
import os

router = APIRouter(tags=["network"])
logger = logging.getLogger(__name__)

def get_db():
    return MetadataDB(app_config.METADATA_DB)

def convert_netmask_to_cidr(netmask: str) -> int:
    """Chuyển đổi netmask (e.g. 255.255.255.0) sang CIDR prefix (e.g. 24)."""
    try:
        parts = [int(p) for p in netmask.split('.')]
        if len(parts) != 4:
            return 24
        binary_str = ''.join([bin(p)[2:].zfill(8) for p in parts])
        return binary_str.count('1')
    except Exception:
        return 24

def run_network_apply_script(config: dict):
    """
    Chạy ngầm việc áp dụng cấu hình mạng LAN/WLAN trên Raspberry Pi.
    """
    logger.info("[Network] Starting network apply script in background thread...")
    # Delay 1.5 giây để đảm bảo API kịp trả về response thành công cho frontend
    time.sleep(1.5)
    
    lan_type = config.get("lan_type", "static")
    lan_ip = config.get("lan_ip", "192.168.1.100")
    lan_gateway = config.get("lan_gateway", "192.168.1.1")
    lan_mask = config.get("lan_mask", "255.255.255.0")
    lan_dns1 = config.get("lan_dns1", "192.168.1.1")
    lan_dns2 = config.get("lan_dns2", "8.8.8.8")
    
    wlan_type = config.get("wlan_type", "dynamic")
    wlan_ip = config.get("wlan_ip", "192.168.43.100")
    wlan_gateway = config.get("wlan_gateway", "192.168.43.1")
    wlan_mask = config.get("wlan_mask", "255.255.255.0")
    wlan_dns1 = config.get("wlan_dns1", "192.168.43.1")
    wlan_dns2 = config.get("wlan_dns2", "8.8.8.8")
    
    wlan_manual = config.get("wlan_manual", "false")
    wlan_ssid = config.get("wlan_manual_ssid") if wlan_manual == "true" else config.get("wlan_ssid")
    wlan_pass = config.get("wlan_pass", "")
    
    # 1. Thử sử dụng NetworkManager (nmcli) - Phổ biến trên RPi OS mới
    try:
        # Kiểm tra xem nmcli có khả dụng không
        check_nmcli = subprocess.run(["which", "nmcli"], capture_output=True, text=True)
        if check_nmcli.returncode == 0:
            logger.info("[Network] NetworkManager (nmcli) detected. Modifying connections...")
            
            # --- Cấu hình LAN (eth0) ---
            # Tìm tên connection LAN
            conn_list = subprocess.run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"], capture_output=True, text=True)
            lan_conn_name = "Wired connection 1" # mặc định
            for line in conn_list.stdout.strip().split('\n'):
                if ':' in line:
                    parts = line.rsplit(':', 1)
                    if len(parts) == 2:
                        c_name, c_dev = parts[0].replace('\\:', ':'), parts[1]
                        if c_dev in ["eth0", "enp3s0", "enp0s31f6"]:
                            lan_conn_name = c_name
                            break
            
            if lan_type == "static":
                cidr = convert_netmask_to_cidr(lan_mask)
                subprocess.run(["nmcli", "connection", "modify", lan_conn_name, 
                                "ipv4.method", "manual", 
                                "ipv4.addresses", f"{lan_ip}/{cidr}", 
                                "ipv4.gateway", lan_gateway, 
                                "ipv4.dns", f"{lan_dns1} {lan_dns2}"], check=True)
            else:
                subprocess.run(["nmcli", "connection", "modify", lan_conn_name, 
                                "ipv4.method", "auto", 
                                "ipv4.addresses", "", 
                                "ipv4.gateway", "", 
                                "ipv4.dns", ""], check=True)
            
            subprocess.run(["nmcli", "connection", "up", lan_conn_name])
            logger.info(f"[Network] LAN connection '{lan_conn_name}' updated.")

            # --- Cấu hình WLAN (wlan0) ---
            if wlan_ssid:
                # Kết nối tới Wifi AP
                connect_cmd = ["nmcli", "device", "wifi", "connect", wlan_ssid]
                if wlan_pass:
                    connect_cmd.extend(["password", wlan_pass])
                
                connect_res = subprocess.run(connect_cmd, capture_output=True, text=True)
                logger.info(f"[Network] Wifi connection attempt: {connect_res.stdout.strip()}")
                
                # Cấu hình IP tĩnh hoặc động cho Wifi Connection vừa tạo
                if connect_res.returncode == 0 or "already active" in connect_res.stderr:
                    if wlan_type == "static":
                        w_cidr = convert_netmask_to_cidr(wlan_mask)
                        subprocess.run(["nmcli", "connection", "modify", wlan_ssid, 
                                        "ipv4.method", "manual", 
                                        "ipv4.addresses", f"{wlan_ip}/{w_cidr}", 
                                        "ipv4.gateway", wlan_gateway, 
                                        "ipv4.dns", f"{wlan_dns1} {wlan_dns2}"], check=True)
                    else:
                        subprocess.run(["nmcli", "connection", "modify", wlan_ssid, 
                                        "ipv4.method", "auto"], check=True)
                        
                    subprocess.run(["nmcli", "connection", "up", wlan_ssid])
                    logger.info(f"[Network] WLAN connection '{wlan_ssid}' updated.")
            return
    except Exception as e:
        logger.warning(f"[Network] nmcli configure failed (perhaps not running or permission denied): {e}")

    # 2. Phương án dự phòng (dhcpcd và wpa_supplicant) - Dành cho Raspberry Pi Bullseye trở về trước
    try:
        # Kiểm tra xem dhcpcd.conf có tồn tại không
        if os.path.exists("/etc/dhcpcd.conf"):
            logger.info("[Network] dhcpcd configuration detected. Writing to /etc/dhcpcd.conf...")
            
            # Đọc file dhcpcd.conf hiện tại
            with open("/etc/dhcpcd.conf", "r") as f:
                lines = f.readlines()
            
            new_lines = []
            skip_interface = False
            for line in lines:
                if line.strip().startswith("interface eth0") or line.strip().startswith("interface wlan0"):
                    skip_interface = True
                    continue
                if skip_interface and line.strip().startswith("interface"):
                    skip_interface = False
                if skip_interface:
                    continue
                new_lines.append(line)
            
            # Thêm cấu hình LAN
            new_lines.append("\ninterface eth0\n")
            if lan_type == "static":
                cidr = convert_netmask_to_cidr(lan_mask)
                new_lines.append(f"static ip_address={lan_ip}/{cidr}\n")
                new_lines.append(f"static routers={lan_gateway}\n")
                new_lines.append(f"static domain_name_servers={lan_dns1} {lan_dns2}\n")
            else:
                new_lines.append("dhcp\n")
                
            # Thêm cấu hình WLAN
            if wlan_ssid:
                new_lines.append("\ninterface wlan0\n")
                if wlan_type == "static":
                    w_cidr = convert_netmask_to_cidr(wlan_mask)
                    new_lines.append(f"static ip_address={wlan_ip}/{w_cidr}\n")
                    new_lines.append(f"static routers={wlan_gateway}\n")
                    new_lines.append(f"static domain_name_servers={wlan_dns1} {wlan_dns2}\n")
                else:
                    new_lines.append("dhcp\n")
            
            # Ghi lại dhcpcd.conf
            # Sử dụng sudo nếu cần, ở đây viết trực tiếp do chạy quyền root
            with open("/etc/dhcpcd.conf", "w") as f:
                f.writelines(new_lines)
                
            # Cấu hình wpa_supplicant.conf
            if wlan_ssid and os.path.exists("/etc/wpa_supplicant/wpa_supplicant.conf"):
                wpa_conf = f"""ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=VN

network={{
    ssid="{wlan_ssid}"
    psk="{wlan_pass}"
}}
"""
                with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w") as f:
                    f.write(wpa_conf)
            
            # Restart service
            subprocess.run(["sudo", "systemctl", "restart", "dhcpcd"], check=True)
            logger.info("[Network] Network configuration updated via dhcpcd.")
            return
    except Exception as e:
        logger.error(f"[Network] dhcpcd configuration failed: {e}")

    logger.warning("[Network] Could not apply network configuration: No supported network manager found.")


@router.get("/wifi-scan")
def wifi_scan(db: MetadataDB = Depends(get_db)):
    """
    Quét danh sách mạng Wifi xung quanh Raspberry Pi.
    """
    wifi_list = []
    
    # 1. Thử dùng nmcli trước
    try:
        cmd = ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "yes"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            lines = res.stdout.strip().split('\n')
            seen_ssids = set()
            for line in lines:
                if not line:
                    continue
                parts = line.split(':')
                if len(parts) >= 2:
                    ssid = parts[0]
                    signal = parts[1]
                    security = parts[2] if len(parts) > 2 else "WPA2"
                    
                    if ssid and ssid not in seen_ssids:
                        seen_ssids.add(ssid)
                        wifi_list.append({
                            "ssid": ssid,
                            "signal": f"{signal}%",
                            "security": security if security else "Open"
                        })
    except Exception as e:
        logger.warning(f"nmcli wifi scan not available or failed: {e}")

    # 2. Nếu nmcli thất bại hoặc không có wifi nào, thử dùng iwlist (dự phòng cho RPi Bullseye trở về trước)
    if not wifi_list:
        res_iw = None
        # Thử gọi iwlist trực tiếp trước (vì Docker chạy root thường không cài sudo)
        try:
            cmd_iw = ["iwlist", "wlan0", "scan"]
            res_iw = subprocess.run(cmd_iw, capture_output=True, text=True, timeout=10)
        except Exception as e:
            logger.warning(f"Direct iwlist call not available: {e}. Trying with sudo...")
            try:
                cmd_iw = ["sudo", "iwlist", "wlan0", "scan"]
                res_iw = subprocess.run(cmd_iw, capture_output=True, text=True, timeout=10)
            except Exception as ex:
                logger.warning(f"iwlist wifi scan with sudo failed: {ex}")
                
        if res_iw and res_iw.returncode == 0:
            try:
                ssid = ""
                signal = ""
                for line in res_iw.stdout.split('\n'):
                    line_str = line.strip()
                    if "Quality=" in line_str:
                        # e.g. Quality=39/70  Signal level=-71 dBm
                        parts = line_str.split("Signal level=")
                        if len(parts) > 1:
                            signal = parts[1].split(" ")[0]
                    if "ESSID:" in line_str:
                        ssid = line_str.split('ESSID:"')[1].rstrip('"')
                        if ssid and ssid not in [w["ssid"] for w in wifi_list]:
                            wifi_list.append({
                                "ssid": ssid,
                                "signal": signal if signal else "80%",
                                "security": "WPA2"
                            })
                            ssid = ""
                            signal = ""
            except Exception as parse_err:
                logger.error(f"Error parsing iwlist output: {parse_err}")

    # 3. Nếu vẫn không có wifi nào tìm thấy (môi trường dev hoặc không có card mạng không dây)
    if not wifi_list:
        logger.info("No wifi network found, returning mockup list for development.")
        wifi_list = [
            {"ssid": "EVN_Office_5G", "signal": "95%", "security": "WPA2"},
            {"ssid": "Solar_Internal_Wifi", "signal": "88%", "security": "WPA2"},
            {"ssid": "HaiDang_Co_Ltd", "signal": "76%", "security": "WPA2"},
            {"ssid": "Suryalog_Datalogger_AP", "signal": "90%", "security": "WPA2"},
            {"ssid": "Guest_Network", "signal": "50%", "security": "Open"}
        ]

    return {"wifi": wifi_list}


@router.get("/settings")
def get_network_settings(db: MetadataDB = Depends(get_db)):
    """
    Lấy các thông số IP/Wifi đang lưu trong SQLite system_settings.
    """
    try:
        settings_dict = {
            "lan_type": db.get_setting("lan_type", "static"),
            "lan_ip": db.get_setting("lan_ip", "192.168.1.100"),
            "lan_gateway": db.get_setting("lan_gateway", "192.168.1.1"),
            "lan_mask": db.get_setting("lan_mask", "255.255.255.0"),
            "lan_dns1": db.get_setting("lan_dns1", "192.168.1.1"),
            "lan_dns2": db.get_setting("lan_dns2", "8.8.8.8"),
            "lan_default": db.get_setting("lan_default", "true") == "true",
            
            "wlan_type": db.get_setting("wlan_type", "dynamic"),
            "wlan_ip": db.get_setting("wlan_ip", "192.168.43.100"),
            "wlan_gateway": db.get_setting("wlan_gateway", "192.168.43.1"),
            "wlan_mask": db.get_setting("wlan_mask", "255.255.255.0"),
            "wlan_dns1": db.get_setting("wlan_dns1", "192.168.43.1"),
            "wlan_dns2": db.get_setting("wlan_dns2", "8.8.8.8"),
            "wlan_ssid": db.get_setting("wlan_ssid", ""),
            "wlan_pass": db.get_setting("wlan_pass", ""),
            "wlan_manual": db.get_setting("wlan_manual", "false") == "true",
            "wlan_manual_ssid": db.get_setting("wlan_manual_ssid", ""),
            "wlan_default": db.get_setting("wlan_default", "false") == "true"
        }
        return settings_dict
    except Exception as e:
        logger.error(f"get_network_settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
def apply_network_settings(
    db: MetadataDB = Depends(get_db),
    body: dict = Body(...)
):
    """
    Lưu cấu hình LAN/WLAN và kích hoạt quá trình áp dụng mạng chạy ngầm.
    """
    try:
        # Lưu các trường vào database SQLite
        for k, v in body.items():
            # Chuển đổi boolean sang chuỗi để lưu vào SQLite
            if isinstance(v, bool):
                val_str = "true" if v else "false"
            else:
                val_str = str(v)
            db.set_setting(k, val_str)
            
        # Chạy ngầm tiến trình áp dụng mạng xuống OS của Pi
        thread = threading.Thread(target=run_network_apply_script, args=(body,))
        thread.daemon = True
        thread.start()
        
        return {"ok": True, "message": "Đã lưu cấu hình mạng. Hệ thống sẽ áp dụng cài đặt mới sau 1.5 giây."}
    except Exception as e:
        logger.error(f"apply_network_settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_live_interface_info(interface_name: str) -> dict:
    """Lấy IP, Netmask, Gateway thực tế của interface từ hệ thống không phụ thuộc psutil hay lệnh ip."""
    info = {"ip": "", "netmask": "", "gateway": "", "dns1": "", "dns2": ""}
    
    # 1. Thử lấy thông tin trên Linux bằng fcntl và /proc/net/route (Không cần thư viện ngoài)
    if os.name != 'nt':
        try:
            import fcntl
            import struct
            import socket
            
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ifname_bytes = interface_name[:15].encode('utf-8')
            
            # Lấy IP
            try:
                # 0x8915 = SIOCGIFADDR
                res_ip = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname_bytes))
                info["ip"] = socket.inet_ntoa(res_ip[20:24])
            except Exception as ip_err:
                logger.debug(f"ioctl IP error for {interface_name}: {ip_err}")
                
            # Lấy Netmask
            try:
                # 0x891b = SIOCGIFNETMASK
                res_mask = fcntl.ioctl(s.fileno(), 0x891b, struct.pack('256s', ifname_bytes))
                info["netmask"] = socket.inet_ntoa(res_mask[20:24])
            except Exception as mask_err:
                logger.debug(f"ioctl Netmask error for {interface_name}: {mask_err}")
            
            # Lấy Gateway từ /proc/net/route
            try:
                if os.path.exists("/proc/net/route"):
                    with open("/proc/net/route", "r") as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 3 and parts[0] == interface_name:
                                dest = parts[1]
                                gw_hex = parts[2]
                                if dest == "00000000": # default gateway
                                    val = int(gw_hex, 16)
                                    info["gateway"] = socket.inet_ntoa(struct.pack("<I", val))
                                    break
            except Exception as gw_err:
                logger.debug(f"Read route error for {interface_name}: {gw_err}")
                
        except Exception as e:
            logger.error(f"Error getting interface info via fcntl: {e}")
            
    # 2. Dự phòng bằng psutil (nếu chạy trên Windows hoặc môi trường có sẵn psutil)
    if not info["ip"]:
        try:
            import psutil
            import socket
            addrs = psutil.net_if_addrs()
            if interface_name in addrs:
                for addr in addrs[interface_name]:
                    if addr.family == socket.AF_INET:
                        info["ip"] = addr.address
                        info["netmask"] = addr.netmask
                        break
        except Exception:
            pass

    return info


def check_interface_type_linux(ifname: str) -> str:
    """Kiểm tra xem interface đang được cấu hình tĩnh (static) hay động (dynamic/dhcp) trên Raspberry Pi."""
    # 1. Thử kiểm tra qua nmcli
    try:
        conn_list = subprocess.run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"], capture_output=True, text=True, timeout=2)
        if conn_list.returncode == 0:
            for line in conn_list.stdout.strip().split('\n'):
                if ':' in line:
                    parts = line.rsplit(':', 1)
                    if len(parts) == 2:
                        c_name, c_dev = parts[0].replace('\\:', ':'), parts[1]
                        if c_dev == ifname:
                            method_res = subprocess.run(["nmcli", "-g", "ipv4.method", "connection", "show", c_name], capture_output=True, text=True, timeout=2)
                            if method_res.returncode == 0:
                                method = method_res.stdout.strip()
                                if method == "manual":
                                    return "static"
                                else:
                                    return "dynamic"
    except Exception:
        pass

    # 2. Dự phòng: Đọc file dhcpcd.conf
    if os.path.exists("/etc/dhcpcd.conf"):
        try:
            with open("/etc/dhcpcd.conf", "r") as f:
                lines = f.readlines()
            
            in_interface = False
            for line in lines:
                line_strip = line.strip()
                if line_strip.startswith(f"interface {ifname}"):
                    in_interface = True
                    continue
                if in_interface and line_strip.startswith("interface"):
                    break
                if in_interface:
                    if line_strip.startswith("static ip_address="):
                        return "static"
        except Exception:
            pass

    # Mặc định: eth0 là static, wlan0 là dynamic
    return "static" if ifname == "eth0" else "dynamic"


def get_live_dns() -> list:
    """Đọc DNS thực tế từ resolv.conf (Linux)."""
    dns_list = []
    if os.path.exists("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.strip().startswith("nameserver"):
                        parts = line.split()
                        if len(parts) > 1:
                            dns_list.append(parts[1])
        except Exception as e:
            logger.error(f"Error reading resolv.conf: {e}")
    if not dns_list:
        dns_list = ["8.8.8.8"]
    # Bổ sung DNS dự phòng để luôn có ít nhất 2 DNS điền lên UI
    if len(dns_list) < 2:
        dns_list.append("8.8.8.8")
    return dns_list


@router.get("/live-status")
def get_network_live_status():
    """
    Đọc thông số IP hiện tại của LAN (eth0) và WAN (wlan0) từ Raspberry Pi.
    """
    try:
        lan_if = "eth0"
        wlan_if = "wlan0"
        
        # Hỗ trợ lấy tên interface trên Windows để phát triển/kiểm thử
        if os.name == 'nt':
            import psutil
            addrs = psutil.net_if_addrs()
            lan_if = next((k for k in addrs.keys() if "ethernet" in k.lower() or "lan" in k.lower() or "vboxnet" in k.lower()), "eth0")
            wlan_if = next((k for k in addrs.keys() if "wi-fi" in k.lower() or "wlan" in k.lower()), "wlan0")

        lan_info = get_live_interface_info(lan_if)
        wlan_info = get_live_interface_info(wlan_if)
        
        # Phát hiện loại IP cấu hình thực tế
        lan_info["type"] = check_interface_type_linux(lan_if)
        wlan_info["type"] = check_interface_type_linux(wlan_if)
        
        dns_list = get_live_dns()
        
        lan_info["dns1"] = dns_list[0] if len(dns_list) > 0 else ""
        lan_info["dns2"] = dns_list[1] if len(dns_list) > 1 else ""
        
        wlan_info["dns1"] = dns_list[0] if len(dns_list) > 0 else ""
        wlan_info["dns2"] = dns_list[1] if len(dns_list) > 1 else ""
        
        # Dữ liệu fallback nếu interface không có IP
        if not lan_info["ip"]:
            lan_info["ip"] = "192.168.1.100" if os.name == 'nt' else "Không có kết nối"
            lan_info["netmask"] = "255.255.255.0"
            lan_info["gateway"] = "192.168.1.1"
            lan_info["dns1"] = "192.168.1.1"
            lan_info["dns2"] = "8.8.8.8"
            
        if not wlan_info["ip"]:
            wlan_info["ip"] = "192.168.43.150" if os.name == 'nt' else "Không có kết nối"
            wlan_info["netmask"] = "255.255.255.0"
            wlan_info["gateway"] = "192.168.43.1"
            wlan_info["dns1"] = "192.168.43.1"
            wlan_info["dns2"] = "8.8.8.8"

        return {
            "lan": lan_info,
            "wlan": wlan_info
        }
    except Exception as e:
        logger.error(f"get_network_live_status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
