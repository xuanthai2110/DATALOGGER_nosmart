

import logging
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException

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
        retries: int = 1,
    ):
        self.port = port
        self.retries = retries

        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=bytesize,
            timeout=timeout,
        )

    # ------------------------------------------------------
    # CONNECTION
    # ------------------------------------------------------
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

    # ------------------------------------------------------
    # RETRY WRAPPER
    # ------------------------------------------------------
    def _retry(self, func, *args, **kwargs):
        last_error = None

        for attempt in range(1, self.retries + 1):
            try:
                response = func(*args, **kwargs)

                # pymodbus sometimes returns ModbusIOException instead of raising
                if isinstance(response, ModbusIOException):
                    last_error = response
                    logger.warning(
                        f"[RTU] Attempt {attempt}/{self.retries} failed: {response}"
                    )
                    continue

                return response

            except Exception as e:
                last_error = e
                logger.warning(
                    f"[RTU] Attempt {attempt}/{self.retries} exception: {e}"
                )

        raise ConnectionError(
            f"[RTU] Communication failed after {self.retries} retries: {last_error}"
        )

    # ------------------------------------------------------
    # READ FUNCTIONS
    # ------------------------------------------------------
    def read_input_registers(self, address: int, count: int, slave: int = 1):
        """
        FC=04
        address must be 0-based (wire address)
        """
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
        """
        FC=03
        """
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

    # ------------------------------------------------------
    # WRITE FUNCTIONS
    # ------------------------------------------------------
    def write_single_register(self, address: int, value: int, slave: int = 1):
        """
        FC=06
        """
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
        """
        FC=16
        """
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

    # Alias để driver gọi write_register cho tiện
    def write_register(self, address: int, value: int, slave: int = 1):
        return self.write_single_register(address, value, slave=slave)