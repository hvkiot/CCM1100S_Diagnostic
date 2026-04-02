import can
import isotp
from udsoncan.client import Client
from udsoncan.connections import PythonCanIsotpConnection
import udsoncan

# --- CONFIG ---
# Instead of a custom class, it's safer to use the built-in
# PythonCanIsotpConnection provided by udsoncan
bus = can.interface.Bus(interface='socketcan', channel='can1', bitrate=250000)

tp_addr = isotp.Address(
    txid=0x1BDA08F1,
    rxid=0x1BDAF108,
    addressing_mode=isotp.AddressingMode.Normal_29bits
)

# Use the library's native connection handler for better compatibility
conn = PythonCanIsotpConnection(bus, address=tp_addr)

# Define client configuration (where timeout actually belongs)
client_config = {
    'request_timeout': 2.0,
    'p2_timeout': 1.0,
    'p2_star_timeout': 5.0
}

with Client(conn, config=client_config) as client:
    try:
        # Test DID 0x220F (Voltage)
        response_220f = client.read_data_by_identifier(0x220F)
        # Note: .data contains the raw bytes after the service/DID
        print(f"DID 0x220F Raw Data: {response_220f.data.hex().upper()}")

        # Test DID 0xF191 (HW Number)
        response_f191 = client.read_data_by_identifier(0xF191)
        print(f"DID 0xF191 Raw Data: {response_f191.data.hex().upper()}")
        # To see the ASCII string:
        print(
            f"DID 0xF191 String: {response_f191.data.decode('ascii', errors='ignore')}")

    except Exception as e:
        print(f"UDS Error: {e}")

# Bus shutdown is handled by the 'with' block or manually:
bus.shutdown()
