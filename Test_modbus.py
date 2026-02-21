from communication.modbus_tcp import ModbusTCP

transport = ModbusTCP(host="192.168.0.110", port=502)

if transport.connect():
    resp = transport.read_input_registers(0, 5, 1)
    print(resp.registers)
    transport.close()