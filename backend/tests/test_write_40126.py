from pymodbus.client import ModbusTcpClient
import argparse
import sys
import time


DEFAULT_IP = "192.168.1.8"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 9
DEFAULT_KW = 50.0
DEFAULT_PERCENT = 45.5
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


def write_40120_kw(client: ModbusTcpClient, slave_id: int, kw: float):
    value = int(round(kw * 10))
    print(f"WRITE 40120 -> kw={kw}, raw={value}, slave_id={slave_id}")
    response = client.write_register(40120, value, slave=slave_id)

    if response.isError():
        print(f"WRITE 40120 FAILED: {response}")
        return False

    print(f"WRITE 40120 OK: {response}")
    return True


def write_40125_percent(client: ModbusTcpClient, slave_id: int, percent: float):
    value = int(round(percent * 10))
    print(f"WRITE 40125 -> percent={percent}, raw={value}, slave_id={slave_id}")
    response = client.write_register(40125, value, slave=slave_id)

    if response.isError():
        print(f"WRITE 40125 FAILED: {response}")
        return False

    print(f"WRITE 40125 OK: {response}")
    return True


def write_40126_watts(client: ModbusTcpClient, slave_id: int, watts: int):
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
        print(f"WRITE 40126 FAILED: {response}")
        return False

    print(f"WRITE 40126 OK: {response}")
    return True


def print_snapshot(client: ModbusTcpClient, slave_id: int, title: str):
    print(f"\n{title}")
    read_limit_block(client, slave_id)
    read_power(client, slave_id)


def run_step(client: ModbusTcpClient, slave_id: int, label: str, fn, readback_delay: float):
    print(f"\n{label}")
    ok = fn()
    print(f"\nWAIT {readback_delay}s BEFORE READBACK")
    time.sleep(readback_delay)
    print_snapshot(client, slave_id, f"AFTER {label}")
    return ok


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test Huawei control registers 40120, 40125, then 40126 via Modbus TCP."
    )
    parser.add_argument("--host", default=DEFAULT_IP, help="Modbus TCP host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Modbus TCP port")
    parser.add_argument("--slave", type=int, default=DEFAULT_SLAVE_ID, help="Modbus slave ID")
    parser.add_argument("--kw", type=float, default=DEFAULT_KW, help="kW value for register 40120")
    parser.add_argument(
        "--percent",
        type=float,
        default=DEFAULT_PERCENT,
        help="Percent value for register 40125",
    )
    parser.add_argument("--watts", type=int, default=DEFAULT_WATTS, help="Watt value for registers 40126-40127")
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
        f"CONNECT -> host={args.host}, port={args.port}, slave_id={args.slave}, "
        f"kw={args.kw}, percent={args.percent}, watts={args.watts}"
    )
    if not client.connect():
        print("CONNECT FAILED")
        sys.exit(1)

    print("CONNECT OK")

    try:
        print_snapshot(client, args.slave, "BEFORE WRITE")

        ok_40120 = run_step(
            client,
            args.slave,
            "TEST WRITE 40120",
            lambda: write_40120_kw(client, args.slave, args.kw),
            args.readback_delay,
        )
        ok_40125 = run_step(
            client,
            args.slave,
            "TEST WRITE 40125",
            lambda: write_40125_percent(client, args.slave, args.percent),
            args.readback_delay,
        )
        ok_40126 = run_step(
            client,
            args.slave,
            "TEST WRITE 40126",
            lambda: write_40126_watts(client, args.slave, args.watts),
            args.readback_delay,
        )

        print("\nSUMMARY")
        print(f"40120: {'OK' if ok_40120 else 'FAILED'}")
        print(f"40125: {'OK' if ok_40125 else 'FAILED'}")
        print(f"40126: {'OK' if ok_40126 else 'FAILED'}")

        if not (ok_40120 and ok_40125 and ok_40126):
            sys.exit(2)
    finally:
        client.close()
        print("\nDISCONNECTED")


if __name__ == "__main__":
    main()
