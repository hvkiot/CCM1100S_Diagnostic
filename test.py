import can
import isotp
from udsoncan.client import Client

bus = can.interface.Bus(interface='socketcan', channel='can1', bitrate=250000)

tp_addr = isotp.Address(
    txid=0x1BDA08F1,
    rxid=0x1BDAF108,
    addressing_mode=isotp.AddressingMode.Normal_29bits
)

stack = isotp.CanStack(bus, address=tp_addr)


class SimpleUDSConnection:
    def __init__(self, stack):
        self.stack = stack

    def send(self, data):
        self.stack.send(bytes(data))

    def receive(self, timeout=2):
        return self.stack.receive(timeout)


conn = SimpleUDSConnection(stack)
client = Client(conn, timeout=2)

# Test your DIDs
response_220f = client.read_data_by_identifier(0x220F)
print(f"DID 0x220F: {response_220f.values[0x220F]}")

response_f191 = client.read_data_by_identifier(0xF191)
print(f"DID 0xF191: {response_f191.values[0xF191]}")
