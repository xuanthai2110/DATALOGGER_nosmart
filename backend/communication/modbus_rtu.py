import time
import random
import logging
import os

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

from backend.communication.modbus_arbiter import ModbusBusArbiter


logger = logging.getLogger(__name__)


class ModbusRTU:
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 9600,
        parity: str = "N",
        stopbits: int = 1,
        bytesize: int = 8,
        timeout: float = 1.0,
        retries: int = None,
        multi_master: bool = False,
        bus_wait_timeout: float = None,
    ):
        self.port = port
        self.multi_master = multi_master
        if retries is not None:
            self.retries = max(retries, 1)
        elif self.multi_master:
            self.retries = 15
        else:
            self.retries = 3

        if bus_wait_timeout is not None:
            self.bus_wait_timeout = bus_wait_timeout
        elif self.multi_master:
            self.bus_wait_timeout = 6.0
        else:
            self.bus_wait_timeout = 2.0
            
        physical_port = os.path.normcase(os.path.realpath(port))
        self.arbiter = ModbusBusArbiter(f"rtu://{physical_port}")
        self.last_master_activity = 0 # Lưu vết thời điểm cuối cùng Master hãng hoạt động
        self.last_our_activity = 0    # Lưu vết thời điểm cuối cùng Datalogger của ta hoạt động

        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=bytesize,
            timeout=timeout,
        )

    def connect(self) -> bool:
        """Probe the serial device under the bus lock, then release it.

        Keeping a serial descriptor open outside an arbiter transaction would
        prevent another process from taking its prioritized turn.
        """
        self.arbiter.acquire()
        try:
            return self._connect_client()
        finally:
            try:
                self.client.close()
            except Exception:
                logger.debug("[RTU] Error closing %s after connection probe", self.port, exc_info=True)
            self.arbiter.release()

    def _connect_client(self) -> bool:
        try:
            # Nếu socket đã tồn tại nhưng cần reconnect, đóng dứt điểm socket cũ trước
            if hasattr(self.client, "close"):
                try:
                    self.client.close()
                except Exception:
                    pass

            # Thử lại kết nối 3 lần để phòng trường hợp OS chưa kịp giải phóng lock cổng serial (Errno 11)
            for attempt in range(1, 4):
                try:
                    if self.client.connect():
                        logger.info(f"[RTU] Connected to {self.port}")
                        return True
                except Exception as e:
                    err_str = str(e)
                    if "Errno 11" in err_str or "exclusively lock" in err_str or "Resource temporarily unavailable" in err_str:
                        logger.warning(f"[RTU] Port {self.port} temporarily locked (Errno 11). Attempt {attempt}/3, retrying in 100ms...")
                        time.sleep(0.1)
                    else:
                        logger.error(f"[RTU] Connect error on {self.port}: {e}")
                        return False

            logger.error(f"[RTU] Cannot open port {self.port} after 3 attempts")
            return False
        except Exception as e:
            logger.error(f"[RTU] Connect error on {self.port}: {e}")
            return False

    def close(self):
        try:
            self.client.close()
            logger.info(f"[RTU] Port closed {self.port}")
        except Exception as e:
            logger.error(f"[RTU] Close error: {e}")

    def _wait_for_bus_free(self, timeout: float = None):
        """Thuật toán Silence Burst: Phải im lặng đủ lâu mới được xả đạn, xả tối đa X giây rồi nghỉ."""
        if not self.multi_master or not hasattr(self.client, "socket") or not self.client.socket:
            return

        effective_timeout = timeout if timeout is not None else getattr(self, "bus_wait_timeout", 6.0)
        burst_duration = 0.8     # Được phép xả nhanh liên tục trong 0.8s
        long_silence_req = 0.5   # Im lặng 0.5s là đủ an toàn để bắt khoảng nghỉ của Hãng (thay vì 1.5s)
        short_silence_req = 0.04 # Giữa các lệnh trong Burst đợi 40ms

        burst_start = getattr(self, 'burst_start_time', 0)
        
        if time.time() - burst_start < burst_duration:
            required_silence = short_silence_req
        else:
            required_silence = long_silence_req

        start_wait = time.time()
        last_bus_activity = time.time() 

        while time.time() - start_wait < effective_timeout:
            try:
                # Nếu có rác hoặc sóng của Hãng
                if self.client.socket.in_waiting > 0:
                    self.client.socket.reset_input_buffer()
                    last_bus_activity = time.time()
                    
                    # Bị Hãng cắt ngang -> Mất quyền Burst ngay lập tức
                    if time.time() - getattr(self, 'burst_start_time', 0) < burst_duration:
                        logger.warning("[RTU] Master interrupted our burst. Burst revoked.")
                        self.burst_start_time = 0
                        
                    required_silence = long_silence_req 
                else:
                    if time.time() - last_bus_activity >= required_silence:
                        if required_silence == long_silence_req:
                            self.burst_start_time = time.time()
                            logger.info(f"[RTU] Bus silent for {long_silence_req}s. ENTERING BURST WINDOW ({burst_duration}s).")
                        return 
            except Exception as e:
                logger.error(f"[RTU] Silence Burst Exception: {e}")
                break
            time.sleep(0.005)
            
        # Khi chạm timeout: Lắng nghe thêm tối đa 0.2s để dọn sạch buffer dư thừa (có hard deadline tránh treo)
        drain_deadline = time.time() + 0.2
        while time.time() < drain_deadline:
            if hasattr(self.client, "socket") and self.client.socket and self.client.socket.in_waiting > 0:
                self.client.socket.reset_input_buffer()
            time.sleep(0.005)
        logger.warning(f"[RTU] Bus wait timeout ({effective_timeout}s), proceeding after wire cleared.")

    def _retry(self, func, *args, retries: int = None, **kwargs):
        last_error = None
        current_mode = self.arbiter.current_mode()

        # Control mode: ưu tiên cao, retry nhiều hơn để vượt qua tranh chấp port
        if retries is None:
            if current_mode == "control":
                effective_retries = 5
            else:
                effective_retries = self.retries
        else:
            effective_retries = max(retries, 1)

        self.arbiter.acquire()
        try:
            for attempt in range(1, effective_retries + 1):
                try:
                    if not getattr(self.client, "connected", False) and not self._connect_client():
                        raise ConnectionError(f"Failed to connect to serial port {self.port}")
                    # 1. Chờ bus rảnh trước khi gửi (LBT)
                    self._wait_for_bus_free()

                    # 2. Xóa buffer trước khi gửi để tránh dữ liệu rác từ master kia
                    if hasattr(self.client, "socket") and self.client.socket:
                        try:
                            self.client.socket.reset_input_buffer()
                        except Exception:
                            pass

                    response = func(*args, **kwargs)
                    self.last_our_activity = time.time()

                    if isinstance(response, ModbusIOException):
                        last_error = response
                        logger.warning(
                            f"[RTU] Attempt {attempt}/{effective_retries} failed: {response}"
                        )
                        if self.multi_master:
                            backoff = random.uniform(0.1, 0.4)
                            logger.info(f"[RTU] Multi-master collision suspected. Backing off for {backoff:.2f}s...")
                            # Tạm nhả khóa Arbiter để luồng Control (nếu có) vào chạy trước trong lúc lùi bước
                            self.arbiter.release()
                            try:
                                time.sleep(backoff)
                            finally:
                                self.arbiter.acquire()
                        elif attempt < effective_retries:
                            time.sleep(0.05)
                        continue

                    if attempt > 1:
                        logger.info(f"[RTU] Success on attempt {attempt}/{effective_retries} for slave {kwargs.get('slave', kwargs.get('unit', '?'))}")
                    
                    return response

                except Exception as e:
                    self.last_our_activity = time.time()
                    last_error = e
                    err_str = str(e)
                    logger.warning(
                        f"[RTU] Attempt {attempt}/{effective_retries} exception: {e}"
                    )

                    is_port_busy = (
                        "Errno 11" in err_str
                        or "exclusively lock" in err_str
                        or "Resource temporarily unavailable" in err_str
                    )
                    is_disconnected = "Failed to connect" in err_str

                    if current_mode == "control":
                        # Control mode: KHÔNG reconnect khi Errno 11 — port đang bị
                        # polling giữ. Chỉ chờ OS/polling release rồi retry.
                        if is_port_busy:
                            wait_sec = 0.15 * attempt  # 150ms, 300ms, 450ms...
                            logger.info(
                                "[RTU] Control mode: port busy (Errno 11), waiting %.2fs before retry %d/%d...",
                                wait_sec, attempt, effective_retries,
                            )
                            time.sleep(wait_sec)
                        elif is_disconnected and attempt < effective_retries:
                            # Mất kết nối thực sự (không phải tranh chấp) → reconnect
                            logger.info(
                                "[RTU] Control mode: connection lost, re-connecting on attempt %d/%d...",
                                attempt, effective_retries,
                            )
                            self._connect_client()
                            time.sleep(0.1)
                        elif attempt < effective_retries:
                            time.sleep(0.1)
                    else:
                        # Polling mode: reconnect như cũ khi bị ngắt kết nối hoặc Errno 11
                        if is_disconnected or is_port_busy:
                            logger.info(
                                "[RTU] Re-connecting serial port %s on attempt %d/%d...",
                                self.port, attempt, effective_retries,
                            )
                            self._connect_client()

                        if self.multi_master:
                            backoff = random.uniform(0.1, 0.4)
                            logger.info(f"[RTU] Exception occurred. Backing off for {backoff:.2f}s...")
                            # Tạm nhả khóa Arbiter để luồng Control (nếu có) vào chạy trước trong lúc lùi bước
                            self.arbiter.release()
                            try:
                                time.sleep(backoff)
                            finally:
                                self.arbiter.acquire()
                        elif attempt < effective_retries:
                            time.sleep(0.1)
        finally:
            # Release the physical serial device with the inter-process lock so
            # the next prioritized request can open it.
            try:
                self.client.close()
            except Exception:
                logger.debug("[RTU] Error closing %s after transaction", self.port, exc_info=True)
            self.arbiter.release()

        raise ConnectionError(
            f"[RTU] Communication failed after {effective_retries} retries: {last_error}"
        )

    def read_input_registers(self, address: int, count: int, slave: int = 1, retries: int = None):
        try:
            return self._retry(
                self.client.read_input_registers,
                address,
                count,
                slave=slave,
                retries=retries,
            )
        except TypeError:
            return self._retry(
                self.client.read_input_registers,
                address,
                count,
                unit=slave,
                retries=retries,
            )

    def read_holding_registers(self, address: int, count: int, slave: int = 1, retries: int = None):
        try:
            return self._retry(
                self.client.read_holding_registers,
                address,
                count,
                slave=slave,
                retries=retries,
            )
        except TypeError:
            return self._retry(
                self.client.read_holding_registers,
                address,
                count,
                unit=slave,
                retries=retries,
            )

    def write_single_register(self, address: int, value: int, slave: int = 1, retries: int = None):
        value = int(value) & 0xFFFF

        try:
            return self._retry(
                self.client.write_register,
                address,
                value,
                slave=slave,
                retries=retries,
            )
        except TypeError:
            return self._retry(
                self.client.write_register,
                address,
                value,
                unit=slave,
                retries=retries,
            )

    def write_multiple_registers(self, address: int, values, slave: int = 1, retries: int = None):
        try:
            return self._retry(
                self.client.write_registers,
                address,
                values,
                slave=slave,
                retries=retries,
            )
        except TypeError:
            return self._retry(
                self.client.write_registers,
                address,
                values,
                unit=slave,
                retries=retries,
            )

    def write_register(self, address: int, value: int, slave: int = 1, retries: int = None):
        return self.write_single_register(address, value, slave=slave, retries=retries)
