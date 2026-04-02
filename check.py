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
    # Determine length
    length = len(payload)

    # -------- Single Frame --------
    if length <= 7:
        data = bytes([length]) + payload + bytes(7 - length)
        send_request(data)

    # -------- First Frame --------
    else:
        first_len = min(6, length)
        ff = bytes([
            0x10 | ((length >> 8) & 0x0F),
            length & 0xFF
        ]) + payload[:first_len]

        ff += bytes(8 - len(ff))
        send_request(ff)

        # Wait for FC
        fc = recv_frame()
        if not fc or (fc[0] >> 4) != 3:
            print("No Flow Control received")
            return None

        # Send Consecutive Frames
        seq = 1
        idx = first_len

        while idx < length:
            chunk = payload[idx:idx+7]
            cf = bytes([0x20 | (seq & 0x0F)]) + chunk
            cf += bytes(8 - len(cf))

            send_request(cf)

            idx += len(chunk)
            seq = (seq + 1) % 16
            time.sleep(0.001)

    # Receive response (reuse your logic)
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


def uds_security_access():
    print("\n--- Security Access ---")

    # Step 1: request seed
    resp = uds_send(bytes([0x27, 0x01]))

    if not resp or resp[0] != 0x67:
        print("Failed to get seed")
        return False

    seed = resp[2:]
    print("Seed:", seed.hex())

    # Step 2: calculate key
    key = calculate_key(seed)
    print("Key:", key.hex())

    # Step 3: send key
    resp = uds_send(bytes([0x27, 0x02]) + key)

    if resp and resp[0] == 0x67:
        print("Security unlocked ✅")
        return True
    else:
        print("Security failed ❌")
        return False


def calculate_key(seed):
    if len(seed) != 16:
        raise ValueError("Seed must be 16 bytes")

    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    key = cipher.encrypt(seed)

    return key


def write_vin(vin):
    vin = vin.strip()
    if len(vin) != 17:
        print(f"VIN must be 17 characters, got {len(vin)}")
        return

    data = vin.encode('ascii')

    uds_write_did(0xF190, data)

# -----------------------------
# 8. TEST
# -----------------------------
# print("\n--- Single Frame DID 0x220F ---")
# uds_read_did(0x220F)

# print("\n--- Multi Frame DID 0xF191 ---")
# uds_read_did(0xF191)


print("\n--- Read DID 0xF190 ---")
uds_read_did(0xF190)

print("\n--- Write DID 0xF190 ---")
uds_send(bytes([0x10, 0x03]))

if uds_security_access():
    # 3. Write VIN
    write_vin("TESTVIN123456789")

# -----------------------------
# 6. CLEANUP
# -----------------------------
bus.shutdown()
print("\nCAN shutdown done.")
