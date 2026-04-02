import can
import isotp
from udsoncan.client import Client
from udsoncan.connections import PythonIsoTpConnection
from udsoncan.services import ReadDataByIdentifier

# Step 1: Setup CAN bus (example: PCAN / SocketCAN / etc.)
bus = can.interface.Bus(
    bustype='socketcan',   # change if needed (pcan, vector, etc.)
    channel='can1',
    bitrate=250000
)

# Step 2: ISO-TP addressing
tp_addr = isotp.Address(
    isotp.AddressingMode.Normal_29bits,
    txid=0x1BDA08F1,   # tester → ECU
    rxid=0x1BDAF108    # ECU → tester
)

# Step 3: ISO-TP stack
stack = isotp.CanStack(
    bus=bus,
    address=tp_addr,
    params={
        'stmin': 32,
        'blocksize': 8,
        'wftmax': 0,
    }
)

conn = PythonIsoTpConnection(stack)

# Step 4: UDS client
with Client(conn, request_timeout=2) as client:

    # ---- Single frame DID ----
    response = client.read_data_by_identifier(0x220F)
    print("0x220F:", response.service_data.values)

    # ---- Multi-frame DID ----
    response = client.read_data_by_identifier(0xF191)
    print("0xF191:", response.service_data.values)
