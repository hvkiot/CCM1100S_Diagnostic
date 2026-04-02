import can
import isotp
import time

# -----------------------------
# 1. CAN BUS SETUP
# -----------------------------
bus = can.interface.Bus(
    interface='socketcan',
    channel='can1',
    bitrate=250000
)

# -----------------------------
# 2. ISO-TP ADDRESS (29-bit)
# -----------------------------
address = isotp.Address(
    isotp.AddressingMode.Normal_29bits,
    txid=0x1BDA08F1,   # Tester → ECU
    rxid=0x1BDAF108    # ECU → Tester
)

# -----------------------------
# 3. ISO-TP STACK
# -----------------------------
stack = isotp.CanStack(
    bus=bus,
    address=address,
    params={
        'stmin': 32,
        'blocksize': 8,
        'wftmax': 0,
    }
)

# -----------------------------
# Helper: send UDS request
# -----------------------------


def uds_request(payload):
    print(f"\nSending: {payload.hex()}")

    stack.send(payload)

    # wait until response is ready
    while True:
        stack.process()
        if stack.available():
            response = stack.recv()
            print(f"Received: {response.hex()}")
            return response
        time.sleep(0.01)

# -----------------------------
# 4. TEST DIDs
# -----------------------------


# ---- Single Frame DID (0x220F) ----
resp_220F = uds_request(bytes([0x22, 0x22, 0x0F]))

# ---- Multi Frame DID (0xF191) ----
resp_F191 = uds_request(bytes([0x22, 0xF1, 0x91]))

# -----------------------------
# 5. OPTIONAL: decode VIN
# -----------------------------
if resp_F191 and resp_F191[0] == 0x62:
    vin_bytes = resp_F191[3:]   # skip 62 F1 91
    try:
        vin = vin_bytes.decode('ascii', errors='ignore')
        print("Decoded VIN:", vin)
    except:
        pass

# -----------------------------
# 6. CLEANUP
# -----------------------------
bus.shutdown()
print("\nCAN shutdown done.")
