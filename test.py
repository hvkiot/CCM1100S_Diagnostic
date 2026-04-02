import can
import isotp
from udsoncan import Client
from udsoncan import services
from udsoncan.connections import IsoTPSocketConnection

# CAN bus setup
bus = can.interface.Bus(bustype='socketcan', channel='can0', bitrate=500000)

# ISO-TP with your specific IDs (physical addressing)
tp_conn = isotp.CanAddressing(
    isotp.AddressingMode.Normal_11bits,
    txid=0x1BDA08F1,  # Your request ID
    rxid=0x1BDAF108   # Your response ID
)

stack = isotp.CanStack(bus, address=tp_conn)
uds_conn = IsoTPSocketConnection(stack)
uds_conn.open()

client = Client(uds_conn, request_timeout=2)

# Test DID 0x220F (single frame - small data)
response_220f = client.read_data_by_identifier(0x220F)
print(f"DID 0x220F (single frame): {response_220f.values[0x220F]}")

# Test DID 0xF191 (multi-frame - needs segmentation)
response_f191 = client.read_data_by_identifier(0xF191)
print(f"DID 0xF191 (multi-frame): {response_f191.values[0xF191]}")

# For functional broadcast request (0x18DB33F1)
# Send raw UDS request without waiting for specific response
functional_msg = can.Message(arbitration_id=0x18DB33F1, data=[
                             0x22, 0x22, 0x0F], is_extended_id=False)
bus.send(functional_msg)
