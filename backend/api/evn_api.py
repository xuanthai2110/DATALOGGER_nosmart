"""
backend/api/evn_api.py — API for global EVN configuration.
"""
from fastapi import APIRouter, Depends, Body
from backend.services.setup_service import SetupService
from backend.api.scan_api import get_setup_service
import logging

router = APIRouter(tags=["evn"])
logger = logging.getLogger(__name__)

@router.get("/settings")
def get_evn_settings(setup_svc: SetupService = Depends(get_setup_service)):
    """Lấy cấu hình EVN toàn cục."""
    return setup_svc.get_evn_settings()

@router.post("/settings")
def update_evn_settings(
    setup_svc: SetupService = Depends(get_setup_service),
    body: dict = Body(...)
):
    """Cập nhật cấu hình EVN toàn cục."""
    host = body.get("host")
    port = int(body.get("port", 502))
    enabled = body.get("enabled", False)
    
    setup_svc.update_evn_settings(host, port, enabled)
    return {"ok": True, "message": "EVN settings updated successfully"}

@router.get("/vpn")
def get_evn_vpn(setup_svc: SetupService = Depends(get_setup_service)):
    """Lấy cấu hình VPN IPsec kết nối EVNNPC."""
    from backend.db_manager import MetadataDB
    from backend.core import settings as app_config
    db = MetadataDB(app_config.METADATA_DB)
    return {
        "vpn_enabled": db.get_setting("vpn_enabled", "false") == "true",
        "vpn_gateway": db.get_setting("vpn_gateway", "116.212.47.2"),
        "vpn_psk": db.get_setting("vpn_psk", "Hdang@0526"),
        "vpn_local_id": db.get_setting("vpn_local_id", "Sophos_EVN"),
        "vpn_remote_id": db.get_setting("vpn_remote_id", "HNM_Hdang"),
        "vpn_local_subnet": db.get_setting("vpn_local_subnet", "10.21.10.64/27"),
        "vpn_remote_subnet": db.get_setting("vpn_remote_subnet", "10.43.248.76/30"),
        "vpn_key_exchange": db.get_setting("vpn_key_exchange", "IKEv2"),
        "vpn_auth_mode": db.get_setting("vpn_auth_mode", "main"),
        
        "vpn_p1_life": int(db.get_setting("vpn_p1_life", "28800")),
        "vpn_p1_margin": int(db.get_setting("vpn_p1_margin", "360")),
        "vpn_p1_dh": db.get_setting("vpn_p1_dh", "14"),
        "vpn_p1_enc": db.get_setting("vpn_p1_enc", "aes256"),
        "vpn_p1_auth": db.get_setting("vpn_p1_auth", "sha256"),
        
        "vpn_p2_dh": db.get_setting("vpn_p2_dh", "14"),
        "vpn_p2_life": int(db.get_setting("vpn_p2_life", "21600")),
        "vpn_p2_enc": db.get_setting("vpn_p2_enc", "aes256"),
        "vpn_p2_auth": db.get_setting("vpn_p2_auth", "sha256")
    }

@router.post("/vpn")
def update_evn_vpn(body: dict = Body(...)):
    """Lưu cấu hình VPN IPsec xuống local database SQLite."""
    from backend.db_manager import MetadataDB
    from backend.core import settings as app_config
    db = MetadataDB(app_config.METADATA_DB)
    for k, v in body.items():
        if isinstance(v, bool):
            val_str = "true" if v else "false"
        else:
            val_str = str(v)
        db.set_setting(k, val_str)
    return {"ok": True, "message": "Đã lưu cấu hình VPN IPsec."}

@router.post("/vpn/apply")
def apply_evn_vpn(body: dict = Body(...)):
    """Áp dụng cấu hình VPN và khởi động lại StrongSwan trên Raspberry Pi."""
    from backend.db_manager import MetadataDB
    from backend.core import settings as app_config
    import subprocess
    import os
    
    db = MetadataDB(app_config.METADATA_DB)
    # Lưu cấu hình trước
    for k, v in body.items():
        if isinstance(v, bool):
            val_str = "true" if v else "false"
        else:
            val_str = str(v)
        db.set_setting(k, val_str)
        
    enabled = body.get("vpn_enabled", False)
    
    if not enabled:
        try:
            subprocess.run(["sudo", "systemctl", "stop", "strongswan-starter"], check=False)
            subprocess.run(["sudo", "ipsec", "stop"], check=False)
        except Exception as e:
            logger.warning(f"Could not stop strongswan: {e}")
        return {"ok": True, "message": "Đã dừng dịch vụ VPN IPsec."}
        
    gateway = body.get("vpn_gateway", "")
    psk = body.get("vpn_psk", "")
    local_id = body.get("vpn_local_id", "")
    remote_id = body.get("vpn_remote_id", "")
    local_subnet = body.get("vpn_local_subnet", "")
    remote_subnet = body.get("vpn_remote_subnet", "")
    key_exchange = body.get("vpn_key_exchange", "IKEv2").lower()
    
    p1_enc = body.get("vpn_p1_enc", "aes256")
    p1_auth = body.get("vpn_p1_auth", "sha256")
    p1_dh = body.get("vpn_p1_dh", "14")
    p1_life = body.get("vpn_p1_life", 28800)
    p1_margin = body.get("vpn_p1_margin", 360)
    
    p2_enc = body.get("vpn_p2_enc", "aes256")
    p2_auth = body.get("vpn_p2_auth", "sha256")
    p2_dh = body.get("vpn_p2_dh", "14")
    p2_life = body.get("vpn_p2_life", 21600)
    
    dh_map = {"2": "modp1024", "5": "modp1536", "14": "modp2048", "none": ""}
    p1_dh_str = f"-{dh_map.get(str(p1_dh), 'modp2048')}" if dh_map.get(str(p1_dh)) else ""
    p2_dh_str = f"-{dh_map.get(str(p2_dh), 'modp2048')}" if dh_map.get(str(p2_dh)) else ""
    
    ike_str = f"{p1_enc}-{p1_auth}{p1_dh_str}!"
    esp_str = f"{p2_enc}-{p2_auth}{p2_dh_str}!"
    
    ipsec_conf_content = f"""# Sinh tự động bởi Solar Datalogger
config setup
    charondebug="ike 2, knl 2, cfg 2"

conn evn-vpn
    keyexchange={key_exchange}
    authby=secret
    left=%defaultroute
    leftid={local_id}
    leftsubnet={local_subnet}
    right={gateway}
    rightid={remote_id}
    rightsubnet={remote_subnet}
    ike={ike_str}
    esp={esp_str}
    ikelifetime={p1_life}s
    keylife={p2_life}s
    margintime={p1_margin}s
    dpdaction=restart
    dpddelay=30s
    dpdtimeout=120s
    auto=start
"""
    
    ipsec_secrets_content = f"""# Sinh tự động bởi Solar Datalogger
{local_id} {remote_id} : PSK "{psk}"
"""
    
    try:
        conf_path = "/etc/ipsec.conf"
        secrets_path = "/etc/ipsec.secrets"
        
        # Dự phòng ghi file ra scratch folder nếu chạy dev trên Windows hoặc không có quyền root
        if not os.access("/etc", os.W_OK):
            conf_path = os.path.join(app_config.ROOT, "scratch", "ipsec.conf")
            secrets_path = os.path.join(app_config.ROOT, "scratch", "ipsec.secrets")
            os.makedirs(os.path.dirname(conf_path), exist_ok=True)
            logger.warning(f"[VPN] No permission to write to /etc. Writing config files to scratch: {conf_path}")
            
        with open(conf_path, "w") as f:
            f.write(ipsec_conf_content)
        with open(secrets_path, "w") as f:
            f.write(ipsec_secrets_content)
            
        if conf_path == "/etc/ipsec.conf":
            subprocess.run(["sudo", "systemctl", "restart", "strongswan-starter"], check=True)
            logger.info("[VPN] StrongSwan service restarted successfully.")
        
        return {"ok": True, "message": "Đã cấu hình và khởi động lại dịch vụ VPN IPsec kết nối EVN."}
    except Exception as e:
        logger.error(f"[VPN] Apply VPN configurations failed: {e}")
        return {"ok": True, "message": f"Đã lưu nhưng không thể khởi động StrongSwan: {e}"}
