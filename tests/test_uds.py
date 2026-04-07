import can
import time
from Crypto.Cipher import AES

# -----------------------------
# 1. CAN SETUP
# -----------------------------
bus = can.interface.Bus(
    interface='socketcan',
    channel='can1',
    bitrate=250000
)

TX_ID = 0x1BDA08F1
RX_ID = 0x1BDAF108

SECRET_KEY = b"TCHRMVHA2BPX3ULC"

# -----------------------------
# 2. SEND UDS REQUEST
# -----------------------------


def send_request(data):
    msg = can.Message(
        arbitration_id=TX_ID,
        data=data,
        is_extended_id=True
    )
    bus.send(msg)
    print(f"[TX] {hex(TX_ID)} {data.hex()}")

# -----------------------------
# 3. RECEIVE FRAME (filtered)
# -----------------------------


def recv_frame(timeout=1):
    start = time.time()
    while time.time() - start < timeout:
        msg = bus.recv(0.01)
        if msg and msg.arbitration_id == RX_ID:
            print(f"[RX] {hex(msg.arbitration_id)} {msg.data.hex()}")
            return msg.data
    return None

# -----------------------------
# 4. MANUAL ISO-TP RECEIVE
# -----------------------------


def uds_read_did(did):
    # Send request (single frame)
    payload = bytes([0x03, 0x22, (did >> 8) & 0xFF, did & 0xFF, 0, 0, 0, 0])
    send_request(payload)

    # Wait for First Frame
    data = recv_frame()
    if not data:
        print("No response")
        return

    pci_type = data[0] >> 4

    # -------------------------
    # SINGLE FRAME
    # -------------------------
    if pci_type == 0:
        length = data[0] & 0x0F
        response = data[1:1+length]
        print("Final:", response.hex())
        return response

    # -------------------------
    # FIRST FRAME (MULTI)
    # -------------------------
    elif pci_type == 1:
        total_len = ((data[0] & 0x0F) << 8) | data[1]
        response = data[2:]

        print(f"First Frame received. Total length: {total_len}")

        # 🔥 Send Flow Control IMMEDIATELY
        fc = can.Message(
            arbitration_id=TX_ID,
            data=bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0]),
            is_extended_id=True
        )
        bus.send(fc)
        print(f"[TX] FC {fc.data.hex()}")

        # Receive Consecutive Frames
        while len(response) < total_len:
            cf = recv_frame()
            if not cf:
                print("Timeout waiting CF")
                return

            if (cf[0] >> 4) == 2:
                response += cf[1:]

        response = response[:total_len]
        print("Final:", response.hex())
        return response

    else:
        print("Unexpected frame")
        return

# -----------------------------
# 5. MANUAL ISO-TP SEND
# -----------------------------


def uds_send(payload):
    length = len(payload)

    # ---- Single Frame ----
    if length <= 7:
        data = bytes([length]) + payload + bytes(7 - length)
        send_request(data)
        return uds_receive_response()

    # ---- First Frame ----
    first_len = min(6, length)
    ff = bytes([
        0x10 | ((length >> 8) & 0x0F),
        length & 0xFF
    ]) + payload[:first_len]

    ff += bytes(8 - len(ff))
    send_request(ff)

    # Wait for Flow Control
    fc = recv_frame()
    if not fc or (fc[0] >> 4) != 3:
        print("No Flow Control received")
        return None

    blocksize = fc[1]
    stmin_raw = fc[2]

    # 🔥 Convert STmin
    if stmin_raw <= 0x7F:
        stmin = stmin_raw / 1000.0   # milliseconds → seconds
    elif 0xF1 <= stmin_raw <= 0xF9:
        stmin = (stmin_raw - 0xF0) / 10000.0  # microseconds
    else:
        stmin = 0

    print(f"Using STmin: {stmin}s")

    # ---- Send Consecutive Frames ----
    seq = 1
    idx = first_len

    while idx < length:
        chunk = payload[idx:idx+7]

        cf = bytes([0x20 | (seq & 0x0F)]) + chunk
        cf += bytes(8 - len(cf))

        send_request(cf)

        idx += len(chunk)
        seq = (seq + 1) % 16

        # 🔥 Respect ECU timing
        time.sleep(stmin)

    return uds_receive_response()

# -----------------------------
# 6. RECEIVE RESPONSE
# -----------------------------


def uds_receive_response():
    data = recv_frame()
    if not data:
        print("No response")
        return None

    pci_type = data[0] >> 4

    # Single Frame
    if pci_type == 0:
        length = data[0] & 0x0F
        return data[1:1+length]

    # First Frame
    elif pci_type == 1:
        total_len = ((data[0] & 0x0F) << 8) | data[1]
        response = data[2:]

        # Send FC
        fc = can.Message(
            arbitration_id=TX_ID,
            data=bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0]),
            is_extended_id=True
        )
        bus.send(fc)

        while len(response) < total_len:
            cf = recv_frame()
            if not cf:
                return None
            if (cf[0] >> 4) == 2:
                response += cf[1:]

        return response[:total_len]

# -----------------------------
# 7. WRITE DID
# -----------------------------


def uds_write_did(did, data_bytes):
    payload = bytes([0x2E, (did >> 8) & 0xFF, did & 0xFF]) + data_bytes

    print(f"\n[WRITE] DID 0x{did:04X} DATA: {data_bytes.hex()}")

    resp = uds_send(payload)

    if not resp:
        print("No response")
        return

    print("Response:", resp.hex())

    # Positive response
    if resp[0] == 0x6E:
        print("Write SUCCESS")

    # Negative response
    elif resp[0] == 0x7F:
        print(f"Negative Response: NRC=0x{resp[2]:02X}")

# -----------------------------
# 8. CHECK IF ALREADY UNLOCKED
# -----------------------------


def is_security_already_granted():
    """Check if security is already unlocked by requesting seed and looking for all-zero response"""
    print("\n--- Checking Security Status ---")

    resp = uds_send(bytes([0x27, 0x01]))

    if not resp or resp[0] != 0x67:
        print("Failed to get seed response")
        return False

    seed = resp[2:]
    print(f"Seed received: {seed.hex()}")

    # Check if seed is all zeros (indicates already unlocked)
    if all(b == 0 for b in seed):
        print("✅ Security is already granted (all-zero seed detected)")
        return True
    else:
        print("🔒 Security is locked (non-zero seed)")
        return False

# -----------------------------
# 9. SECURITY ACCESS (IMPROVED)
# -----------------------------


def uds_security_access():
    print("\n--- Security Access ---")

    # First check if already unlocked
    if is_security_already_granted():
        print("Already unlocked, skipping unlock sequence")
        return True

    # Step 1: request seed (should be non-zero now)
    resp = uds_send(bytes([0x27, 0x01]))

    if not resp or resp[0] != 0x67:
        print("Failed to get seed")
        return False

    seed = resp[2:]

    # Double-check we didn't get all zeros
    if all(b == 0 for b in seed):
        print("Warning: Got all-zero seed even though we thought locked. Security may already be granted.")
        return True

    print("Seed:", seed.hex())

    # Step 2: calculate key
    key = calculate_key(seed)
    print("Key:", key.hex())

    # Small delay before sending key (some ECUs need this)
    time.sleep(0.05)

    # Step 3: send key
    resp = uds_send(bytes([0x27, 0x02]) + key)

    if resp and resp[0] == 0x67:
        print("Security unlocked ✅")
        return True
    elif resp and resp[0] == 0x7F and len(resp) > 2 and resp[2] == 0x24:
        print("⚠️ Request Sequence Error - Security may already be unlocked")
        # Try to verify by reading a protected DID
        test_resp = uds_read_did(0xF190)
        if test_resp:
            print("Successfully read protected DID, assuming unlocked")
            return True
        return False
    else:
        print(
            f"Security failed with response: {resp.hex() if resp else 'None'} ❌")
        return False

# -----------------------------
# 10. CALCULATE KEY
# -----------------------------


def calculate_key(seed):
    if len(seed) != 16:
        raise ValueError("Seed must be 16 bytes")

    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    key = cipher.encrypt(seed)

    return key

# -----------------------------
# 11. WRITE VIN
# -----------------------------


def write_vin(vin):
    vin = vin.strip()
    if len(vin) != 17:
        print(f"VIN must be 17 characters, got {len(vin)}")
        return

    data = vin.encode('ascii')
    uds_write_did(0xF190, data)

# -----------------------------
# 12. RESET SESSION (OPTIONAL)
# -----------------------------


def reset_session():
    """Force a session reset to clear any existing security state"""
    print("\n--- Resetting Session ---")
    # Send diagnostic session default
    resp = uds_send(bytes([0x10, 0x01]))
    if resp and resp[0] == 0x50:
        print("Session reset to default")
        time.sleep(0.1)  # Allow ECU to process
        return True
    else:
        print("Session reset failed or not needed")
        return False

# -----------------------------
# 13. MAIN
# -----------------------------


# ---- Input ----
did_input = input("Enter DID (e.g., F190): ").strip()
value = input("Enter Value: ").strip()

# Optional: Force session reset if previous run left ECU in weird state
force_reset = input("Force session reset? (y/n, default n): ").strip().lower()
if force_reset == 'y':
    reset_session()

# ---- Convert DID ----
try:
    did = int(did_input, 16)
except ValueError:
    print("Invalid DID format")
    bus.shutdown()
    exit()

# ---- Start Diagnostic Session ----
print("\n--- Starting Extended Diagnostic Session ---")
resp = uds_send(bytes([0x10, 0x03]))
if not resp or resp[0] != 0x50:
    print("Failed to start extended session")
    bus.shutdown()
    exit()
print("Extended session active")

# ---- Security Access ----
if uds_security_access():
    # ---- Write ----
    print(f"\n--- Write DID 0x{did:04X} ---")

    if did == 0xF190:
        # VIN must be ASCII 17 chars
        write_vin(value)
    else:
        # Generic write (hex input expected)
        try:
            data = bytes.fromhex(value)
            uds_write_did(did, data)
        except ValueError:
            print("Invalid hex data for write")
else:
    print("Failed to gain security access - aborting write")

# -----------------------------
# 14. CLEANUP
# -----------------------------
bus.shutdown()
print("\nCAN shutdown done.")
