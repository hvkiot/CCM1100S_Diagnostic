#!/usr/bin/env python3
"""
Simple UDS Test - Single Frame (8 bytes) vs Multi-Frame (>8 bytes)
"""

import can
import time

print("="*60)
print("UDS TEST: Single Frame vs Multi-Frame")
print("="*60)

# Connect to CAN
bus = can.Bus(channel='can1', interface='socketcan', bitrate=250000)
print("\n✅ Connected to CAN1")

# ============================================
# PART 1: Send Wake-up (Required for both)
# ============================================
print("\n" + "="*60)
print("STEP 1: Send Wake-up")
print("="*60)

wakeup = can.Message(
    arbitration_id=0x1BDA08F1,
    data=[0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
    is_extended_id=True
)
bus.send(wakeup)
print("Sent: 1BDA08F1#0210010000000000")
time.sleep(0.1)

# Get wake-up response
resp = bus.recv(timeout=0.5)
if resp:
    print(f"Response: {resp.data.hex().upper()}")
print("✅ Wake-up complete")
time.sleep(0.05)

# ============================================
# PART 2: Single Frame DID (0x220F - System Voltage)
# Returns 8 bytes or less
# ============================================
print("\n" + "="*60)
print("PART 2: Single Frame DID (0x220F - System Voltage)")
print("="*60)

# Send request
request = can.Message(
    arbitration_id=0x1BDA08F1,
    data=[0x03, 0x22, 0x22, 0x0F, 0x00, 0x00, 0x00, 0x00],
    is_extended_id=True
)
bus.send(request)
print("\nSent: 1BDA08F1#0322220F00000000")
print("Waiting for response...")

# Get response
response = bus.recv(timeout=1.0)

if response:
    data = response.data
    print(f"\nResponse: {data.hex().upper()}")

    # Parse single frame response
    # Format: [Length, 0x62, DID_H, DID_L, Value_H, Value_L, ...]
    if len(data) >= 5 and data[1] == 0x62:
        value = (data[3] << 8) | data[4]
        voltage = value / 10.0
        print(f"\n✅ DECODED:")
        print(f"   DID: 0x{data[2]:02X}{data[3]:02X}")
        print(f"   Raw Value: {value}")
        print(f"   System Voltage: {voltage:.1f} V")
        print(f"   Frame Type: SINGLE FRAME (≤ 8 bytes)")
    else:
        print(f"\n⚠️  Unexpected response format")
else:
    print("\n❌ No response")

time.sleep(0.5)

# ============================================
# PART 3: Multi-Frame DID (0xF190 - VIN Number)
# Returns more than 8 bytes (17 bytes)
# ============================================
print("\n" + "="*60)
print("PART 3: Multi-Frame DID (0xF190 - VIN Number)")
print("="*60)

# Send request
request = can.Message(
    arbitration_id=0x1BDA08F1,
    data=[0x03, 0x22, 0xF1, 0x90, 0x00, 0x00, 0x00, 0x00],
    is_extended_id=True
)
bus.send(request)
print("\nSent: 1BDA08F1#0322F19000000000")
print("Waiting for first frame...")

# Get first frame
first_frame = bus.recv(timeout=1.0)

if first_frame:
    data = first_frame.data
    print(f"\nFirst Frame: {data.hex().upper()}")

    # Check if it's a first frame (0x10)
    if data[0] == 0x10:
        print("\n📦 MULTI-FRAME DETECTED!")

        # Calculate total length
        total_length = ((data[0] & 0x0F) << 8) | data[1]
        print(f"   Total bytes expected: {total_length}")
        print(f"   First 6 bytes: {data[2:8].hex().upper()}")

        # Send Flow Control
        print("\nSending Flow Control...")
        flow_ctrl = can.Message(
            arbitration_id=0x1BDA08F1,
            data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=True
        )
        bus.send(flow_ctrl)
        print("Sent: 1BDA08F1#3000000000000000")

        # Collect all data
        all_data = bytearray(data[2:8])
        expected_seq = 1

        print("\nReceiving consecutive frames...")

        while len(all_data) < total_length:
            cf = bus.recv(timeout=1.0)
            if cf and cf.arbitration_id == 0x1BDAF108:
                cf_data = cf.data
                print(f"   CF{expected_seq}: {cf_data.hex().upper()}")

                if (cf_data[0] >> 4) == 0x2:  # Consecutive frame
                    seq = cf_data[0] & 0x0F
                    if seq == expected_seq:
                        all_data.extend(cf_data[1:8])
                        expected_seq += 1
                        if expected_seq > 15:
                            expected_seq = 0
                    else:
                        print(
                            f"   ⚠️  Wrong sequence: got {seq}, expected {expected_seq}")
                else:
                    break
            else:
                break

        print(f"\n✅ Complete data received ({len(all_data)} bytes)")
        print(f"   Hex: {all_data.hex().upper()}")

        # Try to decode as ASCII (VIN)
        try:
            vin = all_data.decode('ascii', errors='ignore').strip('\x00')
            if vin:
                print(f"\n   DECODED VIN: {vin}")
            else:
                print(f"\n   DECODED: Not programmed (all zeros)")
        except:
            print(f"\n   DECODED: {all_data.hex().upper()}")

        print(f"\n   Frame Type: MULTI-FRAME (> 8 bytes)")

    else:
        print(f"\n⚠️  Not a multi-frame response")
else:
    print("\n❌ No response")

# ============================================
# SUMMARY
# ============================================
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print("""
✅ Single Frame DID (0x220F): Response ≤ 8 bytes
   - One CAN frame only
   - Fast response
   
✅ Multi-Frame DID (0xF190): Response > 8 bytes  
   - First frame (0x10) + Flow Control (0x30) + Consecutive frames (0x20)
   - Multiple CAN frames
   - Used for VIN, serial numbers, etc.
""")

# Close
bus.shutdown()
print("\n✅ Bus closed")
