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
        self.retries = retries
        self.multi_master = multi_master
        self.arbiter = ModbusBusArbiter(f"rtu://{port}")

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

    def _wait_for_bus_free(self, timeout=3.0, silence_time=0.2):
        """Đợi cho đến khi đường truyền RS485 im lặng (Listen Before Talk)."""
        if not self.multi_master or not hasattr(self.client, "socket") or not self.client.socket:
            return

        # Tối ưu hóa: Nếu kiểm tra lần đầu thấy bus trống, chỉ đợi 5ms để xác nhận rồi đi tiếp
        try:
            if self.client.socket.in_waiting == 0:
                time.sleep(0.05)
                if self.client.socket.in_waiting == 0:
                    return
        except Exception:
            return

        logger.info(f"[RTU] Bus busy on {self.port}, waiting for silence...")
        start_wait = time.time()
        last_activity = time.time()

        while time.time() - start_wait < timeout:
            try:
                if self.client.socket.in_waiting > 0:
                    # Có dữ liệu trên bus, coi như bận
                    self.client.socket.reset_input_buffer()
                    last_activity = time.time()
                else:
                    # Kiểm tra xem bus đã im lặng đủ lâu chưa
                    if time.time() - last_activity >= silence_time:
                        logger.debug(f"[RTU] Bus is now free on {self.port}")
                        return
            except Exception:
                break

            time.sleep(0.01)
        
        logger.warning(f"[RTU] Bus wait timeout ({timeout}s) on {self.port}, proceeding anyway.")

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

                    if isinstance(response, ModbusIOException):
                        last_error = response
                        logger.warning(
                            f"[RTU] Attempt {attempt}/{self.retries} failed: {response}"
                        )
                        # 3. Random backoff khi lỗi (chỉ dùng khi multi-master)
                        if self.multi_master:
                            backoff = random.uniform(0.5, 1.5)
                            logger.info(f"[RTU] Multi-master collision suspected. Backing off for {backoff:.2f}s...")
                            time.sleep(backoff)
                        continue

                    if attempt > 1:
                        logger.info(f"[RTU] Success on attempt {attempt} for slave {kwargs.get('slave', kwargs.get('unit', '?'))}")
                    
                    return response

                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"[RTU] Attempt {attempt}/{self.retries} exception: {e}"
                    )
                    if self.multi_master:
                        backoff = random.uniform(0.5, 1.5)
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
