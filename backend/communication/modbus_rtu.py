import time
import random
import logging

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
        retries: int = 3,
        multi_master: bool = False,
    ):
        self.port = port
        self.retries = max(retries, 1)
        self.multi_master = multi_master
        
        # Tăng cường độ lỳ lợm cho mạng nhiều Inverter
        if self.multi_master:
            self.retries = max(self.retries, 15)
            
        self.arbiter = ModbusBusArbiter(f"rtu://{port}")
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
        try:
            if not self.client.connect():
                logger.error(f"[RTU] Cannot open port {self.port}")
                return False
            logger.info(f"[RTU] Connected to {self.port}")
            return True
        except Exception as e:
            logger.error(f"[RTU] Connect error on {self.port}: {e}")
            return False

    def close(self):
        try:
            self.client.close()
            logger.info(f"[RTU] Port closed {self.port}")
        except Exception as e:
            logger.error(f"[RTU] Close error: {e}")

    def _wait_for_bus_free(self, timeout=12.0):
        """Thuật toán Silence Burst: Phải im lặng đủ lâu mới được xả đạn, xả tối đa X giây rồi nghỉ."""
        if not self.multi_master or not hasattr(self.client, "socket") or not self.client.socket:
            return

        burst_duration = 1.2  # Được phép xả liên tục trong 1.2s (đủ đọc vài inverter)
        long_silence_req = 1.5 # Phải im lặng 1.5s mới được cấp quyền Burst
        short_silence_req = 0.05 # Giữa các lệnh trong Burst đợi 50ms

        burst_start = getattr(self, 'burst_start_time', 0)
        
        if time.time() - burst_start < burst_duration:
            required_silence = short_silence_req
        else:
            required_silence = long_silence_req

        start_wait = time.time()
        last_bus_activity = time.time() 

        while time.time() - start_wait < timeout:
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
            
        logger.warning(f"[RTU] Bus wait timeout ({timeout}s), proceeding anyway.")

    def _retry(self, func, *args, **kwargs):
        last_error = None

        self.arbiter.acquire()
        try:
            for attempt in range(1, self.retries + 1):
                try:
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
                            f"[RTU] Attempt {attempt}/{self.retries} failed: {response}"
                        )
                        # 3. Random backoff khi lỗi (chỉ dùng khi multi-master)
                        if self.multi_master:
                            backoff = random.uniform(0.1, 0.4)
                            logger.info(f"[RTU] Multi-master collision suspected. Backing off for {backoff:.2f}s...")
                            time.sleep(backoff)
                        continue

                    if attempt > 1:
                        logger.info(f"[RTU] Success on attempt {attempt} for slave {kwargs.get('slave', kwargs.get('unit', '?'))}")
                    
                    return response

                except Exception as e:
                    self.last_our_activity = time.time()
                    last_error = e
                    logger.warning(
                        f"[RTU] Attempt {attempt}/{self.retries} exception: {e}"
                    )
                    if self.multi_master:
                        backoff = random.uniform(0.1, 0.4)
                        logger.info(f"[RTU] Exception occurred. Backing off for {backoff:.2f}s...")
                        time.sleep(backoff)
        finally:
            self.arbiter.release()

        raise ConnectionError(
            f"[RTU] Communication failed after {self.retries} retries: {last_error}"
        )

    def read_input_registers(self, address: int, count: int, slave: int = 1):
        try:
            return self._retry(
                self.client.read_input_registers,
                address,
                count,
                slave=slave,
            )
        except TypeError:
            return self._retry(
                self.client.read_input_registers,
                address,
                count,
                unit=slave,
            )

    def read_holding_registers(self, address: int, count: int, slave: int = 1):
        try:
            return self._retry(
                self.client.read_holding_registers,
                address,
                count,
                slave=slave,
            )
        except TypeError:
            return self._retry(
                self.client.read_holding_registers,
                address,
                count,
                unit=slave,
            )

    def write_single_register(self, address: int, value: int, slave: int = 1):
        value = int(value) & 0xFFFF

        try:
            return self._retry(
                self.client.write_register,
                address,
                value,
                slave=slave,
            )
        except TypeError:
            return self._retry(
                self.client.write_register,
                address,
                value,
                unit=slave,
            )

    def write_multiple_registers(self, address: int, values, slave: int = 1):
        try:
            return self._retry(
                self.client.write_registers,
                address,
                values,
                slave=slave,
            )
        except TypeError:
            return self._retry(
                self.client.write_registers,
                address,
                values,
                unit=slave,
            )

    def write_register(self, address: int, value: int, slave: int = 1):
        return self.write_single_register(address, value, slave=slave)
