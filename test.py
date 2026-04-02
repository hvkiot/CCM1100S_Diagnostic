import can
import isotp
import time
import threading

# -----------------------------
# 1. CAN BUS SETUP
# -----------------------------
bus = can.interface.Bus(
    interface='socketcan',
    channel='can1',
    bitrate=250000
)

# -----------------------------
# 2. DEBUG LISTENER (prints all CAN frames)
# -----------------------------


class DebugListener(can.Listener):
    def on_message_received(self, msg):
        direction = "RX"
        print(f"[{direction}] ID: {hex(msg.arbitration_id)}  DATA: {msg.data.hex()}")


notifier = can.Notifier(bus, [DebugListener()])

# -----------------------------
# 3. ISO-TP ADDRESS (29-bit)
# -----------------------------
address = isotp.Address(
    isotp.AddressingMode.Normal_29bits,
    txid=0x1BDA08F1,
    rxid=0x1BDAF108
)

# -----------------------------
# 4. ISO-TP STACK
# -----------------------------
stack = isotp.CanStack(
    bus=bus,
    address=address,
    params={
        'stmin': 0,        # IMPORTANT: allow fastest FC
        'blocksize': 8,
        'wftmax': 0,
        'tx_padding': 0x00,
        'rx_flowcontrol_timeout': 1000,
        'rx_consecutive_frame_timeout': 1000,
    }
)

# -----------------------------
# Helper: send UDS request
# -----------------------------


def uds_request(payload, timeout=2):
    print(f"\nSending UDS: {payload.hex()}")

    stack.send(payload)
    start_time = time.time()

    while True:
        stack.process()

        if stack.available():
            response = stack.recv()
            print(f"\nFinal Reassembled Response: {response.hex()}")
            return response

        if (time.time() - start_time) > timeout:
            print("Timeout waiting for response")
            return None

# -----------------------------
# 5. TEST
# -----------------------------


# Single frame
resp_220F = uds_request(bytes([0x22, 0x22, 0x0F]))

# Multi-frame
resp_F191 = uds_request(bytes([0x22, 0xF1, 0x91]))

# -----------------------------
# 6. OPTIONAL VIN decode
# -----------------------------
if resp_F191 and resp_F191[0] == 0x62:
    vin_bytes = resp_F191[3:]
    try:
        vin = vin_bytes.decode('ascii', errors='ignore')
        print("Decoded VIN:", vin)
    except:
        pass

# -----------------------------
# 7. CLEANUP
# -----------------------------
notifier.stop()
bus.shutdown()
print("\nCAN shutdown done.")
