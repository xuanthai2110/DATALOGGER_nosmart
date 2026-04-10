from pymodbus.client import ModbusTcpClient
import argparse
import sys
import time


DEFAULT_IP = "192.168.1.8"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 9
DEFAULT_WATTS = 50000


def read_limit_block(client: ModbusTcpClient, slave_id: int):
    response = client.read_holding_registers(35300, 4, slave=slave_id)
    if response.isError():
        print(f"READ 35300-35303 FAILED: {response}")
        return None

    regs = response.registers
    mode = regs[0]
    limit_w = (regs[2] << 16) + regs[3]
    print(f"READ 35300-35303 OK: regs={regs}, mode={mode}, limit_w={limit_w}")
    return regs


def read_power(client: ModbusTcpClient, slave_id: int):
    response = client.read_holding_registers(32080, 2, slave=slave_id)
    if response.isError():
        print(f"READ 32080-32081 FAILED: {response}")
        return None

    regs = response.registers
    value = (regs[0] << 16) + regs[1]
    if value > 0x7FFFFFFF:
        value -= 0x100000000

    print(f"READ 32080-32081 OK: regs={regs}, power_w={value}")
    return value


def write_40126(client: ModbusTcpClient, slave_id: int, watts: int):
    watts = int(round(watts))
    high = (watts >> 16) & 0xFFFF
    low = watts & 0xFFFF
    values = [high, low]

    print(
        f"WRITE 40126-40127 -> watts={watts}, high={high}, low={low}, "
        f"values={values}, slave_id={slave_id}"
    )
    response = client.write_registers(40126, values, slave=slave_id)

    if response.isError():
        print(f"WRITE FAILED: {response}")
        return False

    print(f"WRITE OK: {response}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test write multiple registers 40126-40127 via Modbus TCP."
    )
    parser.add_argument("--host", default=DEFAULT_IP, help="Modbus TCP host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Modbus TCP port")
    parser.add_argument("--slave", type=int, default=DEFAULT_SLAVE_ID, help="Modbus slave ID")
    parser.add_argument("--watts", type=int, default=DEFAULT_WATTS, help="Watt limit to write")
    parser.add_argument(
        "--readback-delay",
        type=float,
        default=1.0,
        help="Seconds to wait before readback",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    client = ModbusTcpClient(args.host, port=args.port, timeout=3)

    print(
        f"CONNECT -> host={args.host}, port={args.port}, "
        f"slave_id={args.slave}, watts={args.watts}"
    )
    if not client.connect():
        print("CONNECT FAILED")
        sys.exit(1)

    print("CONNECT OK")

    try:
        print("\nBEFORE WRITE")
        read_limit_block(client, args.slave)
        read_power(client, args.slave)

        print("\nWRITE TEST")
        ok = write_40126(client, args.slave, args.watts)

        print(f"\nWAIT {args.readback_delay}s BEFORE READBACK")
        time.sleep(args.readback_delay)
        time.sleep(5)  # Extra short delay to ensure registers are updated

        print("\nAFTER WRITE")
        read_limit_block(client, args.slave)
        read_power(client, args.slave)

        if not ok:
            sys.exit(2)
    finally:
        client.close()
        print("\nDISCONNECTED")


if __name__ == "__main__":
    main()
