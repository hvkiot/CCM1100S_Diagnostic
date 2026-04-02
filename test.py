# import can
# import time

# # -----------------------------
# # 1. CAN SETUP
# # -----------------------------
# bus = can.interface.Bus(
#     interface='socketcan',
#     channel='can1',
#     bitrate=250000
# )

# TX_ID = 0x1BDA08F1
# RX_ID = 0x1BDAF108

# # -----------------------------
# # 2. SEND UDS REQUEST
# # -----------------------------


# def send_request(data):
#     msg = can.Message(
#         arbitration_id=TX_ID,
#         data=data,
#         is_extended_id=True
#     )
#     bus.send(msg)
#     print(f"[TX] {hex(TX_ID)} {data.hex()}")

# # -----------------------------
# # 3. RECEIVE FRAME (filtered)
# # -----------------------------


# def recv_frame(timeout=1):
#     start = time.time()
#     while time.time() - start < timeout:
#         msg = bus.recv(0.01)
#         if msg and msg.arbitration_id == RX_ID:
#             print(f"[RX] {hex(msg.arbitration_id)} {msg.data.hex()}")
#             return msg.data
#     return None

# # -----------------------------
# # 4. MANUAL ISO-TP RECEIVE
# # -----------------------------


# def uds_read_did(did):
#     # Send request (single frame)
#     payload = bytes([0x03, 0x22, (did >> 8) & 0xFF, did & 0xFF, 0, 0, 0, 0])
#     send_request(payload)

#     # Wait for First Frame
#     data = recv_frame()
#     if not data:
#         print("No response")
#         return

#     pci_type = data[0] >> 4

#     # -------------------------
#     # SINGLE FRAME
#     # -------------------------
#     if pci_type == 0:
#         length = data[0] & 0x0F
#         response = data[1:1+length]
#         print("Final:", response.hex())
#         return response

#     # -------------------------
#     # FIRST FRAME (MULTI)
#     # -------------------------
#     elif pci_type == 1:
#         total_len = ((data[0] & 0x0F) << 8) | data[1]
#         response = data[2:]

#         print(f"First Frame received. Total length: {total_len}")

#         # 🔥 Send Flow Control IMMEDIATELY
#         fc = can.Message(
#             arbitration_id=TX_ID,
#             data=bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0]),
#             is_extended_id=True
#         )
#         bus.send(fc)
#         print(f"[TX] FC {fc.data.hex()}")

#         # Receive Consecutive Frames
#         while len(response) < total_len:
#             cf = recv_frame()
#             if not cf:
#                 print("Timeout waiting CF")
#                 return

#             if (cf[0] >> 4) == 2:
#                 response += cf[1:]

#         response = response[:total_len]
#         print("Final:", response.hex())
#         return response

#     else:
#         print("Unexpected frame")
#         return


# # -----------------------------
# # 5. TEST
# # -----------------------------
# print("\n--- Single Frame DID 0x220F ---")
# uds_read_did(0x220F)

# print("\n--- Multi Frame DID 0xF191 ---")
# uds_read_did(0xF191)

# # -----------------------------
# # 6. CLEANUP
# # -----------------------------
# bus.shutdown()
# print("\nCAN shutdown done.")


import can
import time
import re

bus = can.interface.Bus(
    interface='socketcan',
    channel='can1',
    bitrate=250000
)

TX_ID = 0x1BDA08F1
RX_ID = 0x1BDAF108


def send_request(data):
    msg = can.Message(
        arbitration_id=TX_ID,
        data=data,
        is_extended_id=True
    )
    bus.send(msg)
    print(f"[TX] {hex(TX_ID)} {data.hex()}")


def recv_frame(timeout=1):
    start = time.time()
    while time.time() - start < timeout:
        msg = bus.recv(0.01)
        if msg and msg.arbitration_id == RX_ID:
            print(f"[RX] {hex(msg.arbitration_id)} {msg.data.hex()}")
            return msg.data
    return None


def uds_read_did(did):
    # Single-frame request for ReadDataByIdentifier
    payload = bytes([0x03, 0x22, (did >> 8) & 0xFF, did & 0xFF, 0, 0, 0, 0])
    send_request(payload)

    data = recv_frame()
    if not data:
        print("No response")
        return None

    pci_type = data[0] >> 4

    # ---- Single Frame ----
    if pci_type == 0:
        length = data[0] & 0x0F
        response = data[1:1+length]
        print("Final:", response.hex())
        return response

    # ---- First Frame ----
    elif pci_type == 1:
        total_len = ((data[0] & 0x0F) << 8) | data[1]
        response = data[2:]
        print(f"First Frame received. Total length: {total_len}")

        # Flow Control (send immediately)
        fc = can.Message(
            arbitration_id=TX_ID,
            data=bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0]),
            is_extended_id=True
        )
        bus.send(fc)
        print(f"[TX] FC {fc.data.hex()}")

        # Collect CFs
        while len(response) < total_len:
            cf = recv_frame()
            if not cf:
                print("Timeout waiting CF")
                return None

            if (cf[0] >> 4) == 2:  # Consecutive Frame
                response += cf[1:]

        response = response[:total_len]
        print("Final:", response.hex())
        return response

    else:
        print("Unexpected frame")
        return None


# -----------------------------
# Helper: parse DID input
# -----------------------------
def parse_did(text):
    """
    Accepts:
      f191
      0xf191
      F1 91
      220F
    """
    text = text.strip().lower()

    if text in ("exit", "quit", "q"):
        return None

    # remove spaces
    text = text.replace(" ", "")

    # remove 0x if present
    if text.startswith("0x"):
        text = text[2:]

    if not re.fullmatch(r"[0-9a-f]{1,4}", text):
        raise ValueError("Invalid DID format")

    return int(text, 16)


# -----------------------------
# Interactive loop
# -----------------------------
print("\n=== UDS DID Console (manual ISO-TP) ===")
print("Type DID (e.g., F191, 220F) or 'exit'\n")

try:
    while True:
        user_input = input("DID> ").strip()

        try:
            did = parse_did(user_input)
            if did is None:
                print("Exiting...")
                break

            print(f"\n--- Reading DID 0x{did:04X} ---")
            resp = uds_read_did(did)

            # Optional ASCII decode (useful for VIN etc.)
            if resp and len(resp) > 3 and resp[0] == 0x62:
                try:
                    ascii_data = resp[3:].decode('ascii', errors='ignore')
                    if ascii_data.strip():
                        print("ASCII:", ascii_data)
                except:
                    pass

            print()

        except ValueError as ve:
            print("Invalid input. Try like: F191, 220F, 0xF191")

except KeyboardInterrupt:
    print("\nInterrupted by user")

finally:
    bus.shutdown()
    print("CAN shutdown done.")
