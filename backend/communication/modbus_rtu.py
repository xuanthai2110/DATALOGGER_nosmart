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
        
        # Tăng cường độ lỳ lợm cho mạng nhiều Inverter
        if self.multi_master:
            self.retries = max(self.retries, 15)
            
        self.arbiter = ModbusBusArbiter(f"rtu://{port}")
        self.last_master_activity = 0 # Lưu vết thời điểm cuối cùng Master hãng hoạt động

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

    def _wait_for_master_to_finish(self):
        """Đợi cho đến khi Master hãng truyền xong hoàn toàn (im lặng 100ms) để cập nhật mốc thời gian."""
        last_byte_time = time.time()
        while time.time() - last_byte_time < 0.100: # 100ms im lặng liên tục
            try:
                if self.client.socket.in_waiting > 0:
                    self.client.socket.reset_input_buffer()
                    last_byte_time = time.time()
            except Exception:
                break
            time.sleep(0.005)
        self.last_master_activity = time.time()
        logger.info("[RTU] Master finished transaction. Safe 5-second window started.")

    def _wait_for_bus_free(self, timeout=3.0, silence_time=0.040):
        """Đợi cho đến khi đường truyền RS485 im lặng (Listen Before Talk)."""
        if not self.multi_master or not hasattr(self.client, "socket") or not self.client.socket:
            return

        # CHIẾN THUẬT ĐỒNG BỘ NÉ TRÁNH (DANGER ZONE AVOIDANCE)
        # Chu kỳ của Master hãng là đúng 5 giây. 
        # Nếu đã quá 3 giây kể từ lần cuối Master hoạt động, ta đã đi vào VÙNG NGUY HIỂM.
        # Ta phải NHƯỜNG đường, đợi Master bắn lệnh xong rồi bám đuôi ngay sau nó.
        time_since_master = time.time() - getattr(self, 'last_master_activity', 0)
        
        if time_since_master > 3.0:
            logger.info(f"[RTU] Near Master's 5s boundary ({time_since_master:.1f}s elapsed). Waiting for Master to poll first...")
            start_wait = time.time()
            master_detected = False
            while time.time() - start_wait < 6.0: # Đợi tối đa 6s (chu kỳ Master là 5s)
                try:
                    if self.client.socket.in_waiting > 0:
                        master_detected = True
                        break
                except Exception:
                    break
                time.sleep(0.01)
            
            if master_detected:
                self._wait_for_master_to_finish()
            else:
                # Nếu không thấy Master hoạt động (Master offline hoặc ta là duy nhất)
                # Giả lập mốc thời gian để không bị block ở các lệnh tiếp theo
                self.last_master_activity = time.time()
                logger.info("[RTU] No active Master detected. Proceeding.")

        # LBT tiêu chuẩn: Đợi 40ms im lặng
        start_wait = time.time()
        last_activity = time.time()

        while time.time() - start_wait < timeout:
            try:
                if self.client.socket.in_waiting > 0:
                    # Phát hiện Master hãng chen ngang, đợi nó truyền xong rồi reset timer
                    self._wait_for_master_to_finish()
                    last_activity = time.time()
                else:
                    # Kiểm tra xem bus đã im lặng đủ 40ms chưa
                    if time.time() - last_activity >= silence_time:
                        return
            except Exception as e:
                logger.error(f"[RTU] LBT Exception: {e}")
                break

            time.sleep(0.002) # Quét nhạy bén cấp mili-giây
        
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
