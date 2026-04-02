import can
import isotp
from udsoncan.client import Client
from udsoncan.connections import PythonIsoTpConnection
from udsoncan import configs

# -----------------------------
# 1. CAN BUS SETUP (Raspberry Pi SocketCAN)
# -----------------------------
bus = can.interface.Bus(
    interface='socketcan',   # ✅ updated (no deprecation warning)
    channel='can1',
    bitrate=250000
)

# -----------------------------
# 2. ISO-TP ADDRESSING (29-bit IDs)
# -----------------------------
tp_addr = isotp.Address(
    isotp.AddressingMode.Normal_29bits,
    txid=0x1BDA08F1,   # Tester → ECU (RAS)
    rxid=0x1BDAF108    # ECU → Tester
)

# -----------------------------
# 3. ISO-TP STACK
# -----------------------------
stack = isotp.CanStack(
    bus=bus,
    address=tp_addr,
    params={
        'stmin': 32,        # separation time (can tune)
        'blocksize': 8,
        'wftmax': 0,
    }
)

conn = PythonIsoTpConnection(stack)

# -----------------------------
# 4. UDS CLIENT CONFIG
# -----------------------------
config = configs.default_client_config.copy()

# Disable strict DID decoding (IMPORTANT FIX)
config['data_identifiers'] = {}

# -----------------------------
# 5. RUN TEST
# -----------------------------
with Client(conn, request_timeout=2, config=config) as client:

    print("\n--- Testing Single Frame DID (0x220F) ---")
    try:
        response = client.read_data_by_identifier(0x220F)
        print("Raw response (hex):", response.original_payload.hex())
    except Exception as e:
        print("Error:", e)

    print("\n--- Testing Multi Frame DID (0xF191) ---")
    try:
        response = client.read_data_by_identifier(0xF191)
        print("Raw response (hex):", response.original_payload.hex())

        # Optional: try decode as ASCII (VIN usually)
        try:
            ascii_data = bytes.fromhex(response.original_payload.hex()[
                                       6:]).decode('ascii', errors='ignore')
            print("Decoded ASCII:", ascii_data)
        except:
            pass

    except Exception as e:
        print("Error:", e)

# -----------------------------
# 6. CLEAN SHUTDOWN
# -----------------------------
bus.shutdown()
print("\nCAN bus shutdown complete.")
