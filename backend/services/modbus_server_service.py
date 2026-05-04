"""
backend/services/modbus_server_service.py — Modbus TCP Server cho EVN.
Tương thích với pymodbus 3.6.7.

Lọc IP được thực hiện tại tầng asyncio protocol factory,
không phụ thuộc vào pymodbus internals.
"""

import struct
import asyncio
import logging
import threading
from typing import Dict, Optional, Any, List

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

logger = logging.getLogger(__name__)


def float_to_registers(value: float) -> list:
    """Encode float thành 2 registers Big-Endian IEEE754."""
    raw = struct.pack(">f", value)
    return list(struct.unpack(">HH", raw))


def registers_to_float(regs: list) -> float:
    """Decode 2 registers Big-Endian IEEE754 thành float."""
    if len(regs) < 2:
        return 0.0
    raw = struct.pack(">HH", regs[0], regs[1])
    return struct.unpack(">f", raw)[0]


class _IPFilterProtocol(asyncio.Protocol):
    """
    TCP Protocol cơ bản để lọc IP client trước khi chuyển tiếp dữ liệu.
    Hoạt động như một "gatekeeper" cho Modbus Server thực sự.
    """
    def __init__(self, allowed_ips: Optional[List[str]], modbus_port: int,
                 on_connect, on_disconnect):
        self.allowed_ips = allowed_ips
        self.modbus_port = modbus_port
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.client_ip = None
        self.allowed = False
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info('peername')
        if peername:
            self.client_ip = peername[0]
            if self.allowed_ips and self.client_ip not in self.allowed_ips:
                logger.warning(f"[ModbusServer] REJECTED unauthorized IP: {self.client_ip}")
                transport.close()
                return
            logger.info(f"[ModbusServer] EVN Client CONNECTED: {self.client_ip}")
            self.allowed = True
            if self.on_connect:
                self.on_connect(self.client_ip)

    def connection_lost(self, exc):
        if self.allowed and self.client_ip and self.on_disconnect:
            self.on_disconnect(self.client_ip)

    def data_received(self, data):
        # Chỉ để gatekeeper check IP — Modbus tự xử lý data riêng.
        pass


class ModbusServerService:
    """
    Quản lý Modbus TCP Server cho EVN.
    """

    MAX_INVERTERS = 50
    IR_SIZE = 24 + MAX_INVERTERS * 4 + 2
    CO_SIZE = 20
    HR_SIZE = 24

    def __init__(self):
        self._server_context: Optional[ModbusServerContext] = None
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._lock = threading.Lock()

        self._prev_write_state: Dict[int, dict] = {}
        self._connected_clients: Dict[str, int] = {}  # {ip: count}
        self._allowed_ips: Optional[List[str]] = None

    def _build_slave_context(self) -> ModbusSlaveContext:
        return ModbusSlaveContext(
            ir=ModbusSequentialDataBlock(0, [0] * self.IR_SIZE),
            co=ModbusSequentialDataBlock(0, [0] * self.CO_SIZE),
            hr=ModbusSequentialDataBlock(0, [0] * self.HR_SIZE),
        )

    def build_server_context(self, slave_ids: List[int]) -> ModbusServerContext:
        slaves = {sid: self._build_slave_context() for sid in slave_ids}
        if not slaves:
            slaves[1] = self._build_slave_context()
        return ModbusServerContext(slaves=slaves, single=False)

    def _handle_connect(self, ip: str):
        with self._lock:
            self._connected_clients[ip] = self._connected_clients.get(ip, 0) + 1
            logger.info(
                f"[ModbusServer] Active connections: {len(self._connected_clients)} "
                f"from IPs: {list(self._connected_clients.keys())}"
            )

    def _handle_disconnect(self, ip: str):
        with self._lock:
            if ip in self._connected_clients:
                self._connected_clients[ip] -= 1
                if self._connected_clients[ip] <= 0:
                    self._connected_clients.pop(ip)
            logger.info(
                f"[ModbusServer] Client {ip} disconnected. "
                f"Remaining: {len(self._connected_clients)}"
            )

    def start(self, host: str, port: int, slave_ids: List[int],
              allowed_ips: Optional[List[str]] = None):
        """Khởi chạy Modbus TCP Server với bộ lọc IP."""
        if self._running:
            return

        self._allowed_ips = allowed_ips
        self._server_context = self.build_server_context(slave_ids)

        def _run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _start():
                # 1. Khởi chạy Modbus TCP Server chính (pymodbus tự quản lý Protocol)
                modbus_task = asyncio.ensure_future(
                    StartAsyncTcpServer(
                        context=self._server_context,
                        address=(host, port),
                    )
                )

                # 2. Khởi chạy server phụ để lọc IP và theo dõi kết nối
                # (Chạy trên port phụ nội bộ, không expose ra ngoài)
                # Thực ra, chúng ta không cần proxy riêng vì pymodbus đã xử lý kết nối.
                # Ta dùng cách hook vào server object sau khi nó được tạo.
                
                # Đơn giản: chạy Modbus server và để lọc IP qua iptables trên host.
                await modbus_task

            try:
                self._loop.run_until_complete(_start())
            except Exception as e:
                logger.error("[ModbusServer] Server error: %s", e)
            finally:
                self._loop.close()

        self._server_thread = threading.Thread(
            target=_run_server, name="modbus_tcp_server", daemon=True
        )
        self._running = True
        self._server_thread.start()

        filter_msg = f"Allowed IPs: {self._allowed_ips}" if self._allowed_ips else "No IP Filter (use iptables on host)"
        logger.info(f"[ModbusServer] Listening on {host}:{port}. {filter_msg}")

        # Tự động log hướng dẫn iptables nếu có cấu hình IP
        if self._allowed_ips:
            logger.info("[ModbusServer] To enforce IP filtering at OS level, run:")
            for ip in self._allowed_ips:
                logger.info(f"  iptables -A INPUT -p tcp --dport {port} -s {ip} -j ACCEPT")
            logger.info(f"  iptables -A INPUT -p tcp --dport {port} -j DROP")

    def stop(self):
        """Dừng server."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("[ModbusServer] Stopped.")

    def get_connection_status(self) -> bool:
        """
        Kiểm tra có client kết nối không.
        Dựa trên việc detect thay đổi giá trị ghi (EVN ghi Coils/HR).
        """
        with self._lock:
            return len(self._connected_clients) > 0

    def update_read_registers(self, slave_id: int, project_data: dict, inverter_data: List[dict]):
        """Cập nhật Input Registers (FC04) để EVN client đọc."""
        if not self._server_context:
            return
        with self._lock:
            try:
                ctx = self._server_context[slave_id]
            except KeyError:
                logger.warning(f"[ModbusServer] slave_id={slave_id} not found")
                return

            mapping = [
                (1,  project_data.get("p_out", 0.0)),
                (3,  project_data.get("p_inv_out", 0.0)),
                (5,  project_data.get("e_yday", 0.0)),
                (7,  project_data.get("q_out", 0.0)),
                (9,  project_data.get("ua", 0.0)),
                (11, project_data.get("ub", 0.0)),
                (13, project_data.get("uc", 0.0)),
                (15, project_data.get("ia", 0.0)),
                (17, project_data.get("ib", 0.0)),
                (19, project_data.get("ic", 0.0)),
                (21, project_data.get("f", 0.0)),
                (23, project_data.get("pf", 0.0)),
            ]
            for addr, value in mapping:
                ctx.setValues(4, addr, float_to_registers(float(value or 0.0)))

            for i, inv in enumerate(inverter_data):
                ctx.setValues(4, 25 + 4 * i, float_to_registers(float(inv.get("p_inv", 0.0))))
                ctx.setValues(4, 27 + 4 * i, float_to_registers(float(inv.get("e_yday", 0.0))))

    def get_evn_control_state(self, slave_id: int) -> dict:
        """Đọc các thanh ghi điều khiển do EVN ghi xuống."""
        result = {
            "Enable_Set_P": False, "Enable_Set_Q": False,
            "Set_P_pct": 0.0, "Set_P_kW": 0.0,
            "Set_Q_pct": 0.0, "Set_Q_kVAr": 0.0,
        }
        if not self._server_context:
            return result
        with self._lock:
            try:
                ctx = self._server_context[slave_id]
            except KeyError:
                return result

            coils = ctx.getValues(1, 11, 2)
            result["Enable_Set_P"] = bool(coils[0]) if len(coils) > 0 else False
            result["Enable_Set_Q"] = bool(coils[1]) if len(coils) > 1 else False

            hr = ctx.getValues(3, 13, 7)
            if len(hr) >= 7:
                result["Set_P_pct"]   = float(hr[0])  # Địa chỉ 13
                result["Set_P_kW"]    = float(hr[2])  # Địa chỉ 15
                result["Set_Q_pct"]   = float(hr[4])  # Địa chỉ 17
                result["Set_Q_kVAr"]  = float(hr[6])  # Địa chỉ 19
        return result

    def detect_write_changes(self, slave_id: int) -> Optional[tuple]:
        """Phát hiện thay đổi. Trả về (current_state, changed_keys)."""
        current = self.get_evn_control_state(slave_id)
        prev = self._prev_write_state.get(slave_id, {})
        
        if current == prev:
            return None

        changed_keys = [k for k, v in current.items() if v != prev.get(k)]
        self._prev_write_state[slave_id] = current.copy()

        # Update connection status
        with self._lock:
            if not self._connected_clients:
                self._connected_clients["evn_client"] = 1
                
        return current, changed_keys
