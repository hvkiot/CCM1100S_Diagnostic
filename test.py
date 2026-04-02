import can
import time

# Connect to CAN bus
bus = can.Bus(channel='can1', interface='socketcan', bitrate=250000)

# Send wake-up command
msg = can.Message(arbitration_id=0x1BDA08F1, data=[
                  0x02, 0x10, 0x01, 0, 0, 0, 0, 0], is_extended_id=True)
bus.send(msg)
print("Sent: 02 10 01 00 00 00 00 00")

# Wait a bit
time.sleep(0.05)

# Send DID request for 0x220F (Voltage)
msg = can.Message(arbitration_id=0x1BDA08F1, data=[
                  0x03, 0x22, 0x22, 0x0F, 0, 0, 0, 0], is_extended_id=True)
bus.send(msg)
print("Sent: 03 22 22 0F 00 00 00 00")

# Close
bus.shutdown()
