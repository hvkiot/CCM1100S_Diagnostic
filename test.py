import can
import isotp
from udsoncan.client import Client
from udsoncan import services
from udsoncan.connections import IsoTPSocketConnection

# Fix deprecation warning - use 'interface' instead of 'bustype'
bus = can.interface.Bus(interface='socketcan', channel='can0', bitrate=500000)

# Correct isotp addressing for your IDs
tp_addr = isotp.Address(
    txid=0x1BDA08F1,   # Your request ID
    rxid=0x1BDAF108,   # Your response ID
    addressing_mode=isotp.AddressingMode.Normal_11bits
)

stack = isotp.CanStack(bus, address=tp_addr)
uds_conn = IsoTPSocketConnection(stack)
uds_conn.open()

client = Client(uds_conn, request_timeout=2)

# Test your DIDs
response_220f = client.read_data_by_identifier(0x220F)
print(f"DID 0x220F: {response_220f.values[0x220F]}")

response_f191 = client.read_data_by_identifier(0xF191)
print(f"DID 0xF191: {response_f191.values[0xF191]}")
