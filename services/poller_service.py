from drivers.sungrowsg110cx_driver import SungrowSG110CXDriver
from communication.modbus_rtu import ModbusRTU
import config

class PollerService:
    def __init__(self, buffer_service):
        transport = ModbusRTU(
            port=config.MODBUS_PORT,
            baudrate=config.MODBUS_BAUDRATE,
            parity=config.PARITY,
            stopbits=config.STOPBITS,
            timeout=config.TIMEOUT,
            retries=config.RETRIES,
        )   
        transport.connect()
        self.driver = SungrowSG110CXDriver(transport=transport, slave_id=config.SLAVE_ID)
        self.buffer = buffer_service

    def poll(self):
        data = self.driver.read_all()
        self.buffer.save(data)