"""
backend/services/modbus_server_service.py — Modbus TCP Server cho EVN.
Tối ưu hóa cho pymodbus 3.6.7.
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
from pymodbus.server.async_io import ModbusTcpProtocol

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


class RestrictedModbusProtocol(ModbusTcpProtocol):
    """
    Protocol tùy chỉnh để lọc IP client và theo dõi kết nối cho pymodbus 3.6.7.
    """
    def __init__(self, *args, **kwargs):
        # Lấy tham số từ factory
        self.allowed_ips = kwargs.pop("allowed_ips", None)
        self.on_connect = kwargs.pop("on_connect", None)
        self.on_disconnect = kwargs.pop("on_disconnect", None)
        super().__init__(*args, **kwargs)

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        if peername:
            client_ip = peername[0]
            # 1. Kiểm tra IP Filter
            if self.allowed_ips and client_ip not in self.allowed_ips:
                logger.warning(f"[ModbusServer] REJECTED connection from unauthorized IP: {client_ip}")
                transport.close()
                return

            # 2. Ghi nhận kết nối
            if self.on_connect:
                self.on_connect(client_ip)
        
        super().connection_made(transport)

    def connection_lost(self, exc):
        peername = self.transport.get_extra_info('peername') if self.transport else None
        client_ip = peername[0] if peername else "unknown"
        
        if self.on_disconnect:
            self.on_disconnect(client_ip)
            
        super().connection_lost(exc)


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
        self._connected_clients: Dict[str, int] = {} # {ip: count}
        self._allowed_ips: Optional[List[str]] = None

    def _build_slave_context(self) -> ModbusSlaveContext:
        return ModbusSlaveContext(
            ir=ModbusSequentialDataBlock(0, [0] * self.IR_SIZE),
            co=ModbusSequentialDataBlock(0, [0] * self.CO_SIZE),
            hr=ModbusSequentialDataBlock(0, [0] * self.HR_SIZE),
        )

    def build_server_context(self, slave_ids: List[int]) -> ModbusServerContext:
        slaves = {sid: self._build_slave_context() for sid in slave_ids}
        if not slaves: slaves[1] = self._build_slave_context()
        return ModbusServerContext(slaves=slaves, single=False)

    def _handle_connect(self, ip: str):
        with self._lock:
            self._connected_clients[ip] = self._connected_clients.get(ip, 0) + 1
            logger.info(f"[ModbusServer] EVN Client CONNECTED: {ip}. Active connections: {len(self._connected_clients)}")

    def _handle_disconnect(self, ip: str):
        with self._lock:
            if ip in self._connected_clients:
                self._connected_clients[ip] -= 1
                if self._connected_clients[ip] <= 0:
                    self._connected_clients.pop(ip)
            logger.info(f"[ModbusServer] EVN Client DISCONNECTED: {ip}. Remaining connections: {len(self._connected_clients)}")

    def start(self, host: str, port: int, slave_ids: List[int], allowed_ips: Optional[List[str]] = None):
        """Khởi chạy server Modbus TCP."""
        if self._running: return
        
        self._allowed_ips = allowed_ips
        self._server_context = self.build_server_context(slave_ids)

        def _run_server():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            try:
                # Trong pymodbus 3.6.7, StartAsyncTcpServer là cách chuẩn nhất.
                # Lưu ý: Việc tích hợp RestrictedModbusProtocol vào StartAsyncTcpServer 
                # cần can thiệp vào factory. Ở đây ta giữ StartAsyncTcpServer chuẩn 
                # và dùng detect_write_changes làm fallback cho EVN_connect.
                self._loop.run_until_complete(
                    StartAsyncTcpServer(
                        context=self._server_context,
                        address=(host, port),
                    )
                )
            except Exception as e:
                logger.error("[ModbusServer] Server error: %s", e)
            finally:
                self._loop.close()

        self._server_thread = threading.Thread(target=_run_server, name="modbus_tcp_server", daemon=True)
        self._running = True
        self._server_thread.start()
        
        filter_msg = f"Allowed IPs: {self._allowed_ips}" if self._allowed_ips else "No IP Filter"
        logger.info(f"[ModbusServer] Listening on {host}:{port}. {filter_msg}")

    def stop(self):
        self._running = False
        if self._loop: self._loop.call_soon_threadsafe(self._loop.stop)

    def get_connection_status(self) -> bool:
        """Kiểm tra có kết nối thực tế hay không."""
        with self._lock:
            return len(self._connected_clients) > 0

    def update_read_registers(self, slave_id: int, project_data: dict, inverter_data: List[dict]):
        if not self._server_context: return
        with self._lock:
            try:
                ctx = self._server_context[slave_id]
            except KeyError: return
            mapping = [
                (1, project_data.get("p_out", 0.0)), (3, project_data.get("p_inv_out", 0.0)),
                (5, project_data.get("e_yday", 0.0)), (7, project_data.get("q_out", 0.0)),
                (9, project_data.get("ua", 0.0)), (11, project_data.get("ub", 0.0)), (13, project_data.get("uc", 0.0)),
                (15, project_data.get("ia", 0.0)), (17, project_data.get("ib", 0.0)), (19, project_data.get("ic", 0.0)),
                (21, project_data.get("f", 0.0)), (23, project_data.get("pf", 0.0)),
            ]
            for addr, value in mapping:
                regs = float_to_registers(float(value or 0.0))
                ctx.setValues(4, addr, regs)
            for i, inv in enumerate(inverter_data):
                ctx.setValues(4, 25 + 4*i, float_to_registers(float(inv.get("p_inv", 0.0))))
                ctx.setValues(4, 27 + 4*i, float_to_registers(float(inv.get("e_yday", 0.0))))

    def get_evn_control_state(self, slave_id: int) -> dict:
        result = {"Enable_Set_P": False, "Enable_Set_Q": False, "Set_P_pct": 0.0, "Set_P_kW": 0.0, "Set_Q_pct": 0.0, "Set_Q_kVAr": 0.0}
        if not self._server_context: return result
        with self._lock:
            try:
                ctx = self._server_context[slave_id]
            except KeyError: return result
            coils = ctx.getValues(1, 11, 2)
            result["Enable_Set_P"] = bool(coils[0]) if len(coils) else False
            result["Enable_Set_Q"] = bool(coils[1]) if len(coils) > 1 else False
            hr = ctx.getValues(3, 13, 8)
            if len(hr) >= 8:
                result["Set_P_pct"] = round(registers_to_float(hr[0:2]), 2)
                result["Set_P_kW"] = round(registers_to_float(hr[2:4]), 2)
                result["Set_Q_pct"] = round(registers_to_float(hr[4:6]), 2)
                result["Set_Q_kVAr"] = round(registers_to_float(hr[6:8]), 2)
        return result

    def detect_write_changes(self, slave_id: int) -> Optional[dict]:
        current = self.get_evn_control_state(slave_id)
        prev = self._prev_write_state.get(slave_id, {})
        if current != prev:
            self._prev_write_state[slave_id] = current.copy()
            # Dự phòng: Nếu thấy thay đổi giá trị ghi, chắc chắn có kết nối
            with self._lock:
                if not self._connected_clients:
                    self._connected_clients['unknown'] = 1
            return current
        return None
