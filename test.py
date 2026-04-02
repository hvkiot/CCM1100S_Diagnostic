# test.py
import can
import time

# Configuration
CHANNEL = 'can1'
BITRATE = 250000
REQUEST_ID = 0x1BDA08F1
RESPONSE_ID = 0x1BDAF108


def send_cmd(bus, data_list):
    """Send CAN command"""
    msg = can.Message(
        arbitration_id=REQUEST_ID,
        data=data_list,
        is_extended_id=True
    )
    bus.send(msg)
    data_bytes = bytes(data_list)
    print(f"  Sent: {data_bytes.hex().upper()}")


def receive_response(bus, timeout=1.5):
    """Receive CAN response"""
    start = time.time()
    while time.time() - start < timeout:
        msg = bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == RESPONSE_ID:
            return msg.data
    return None


def parse_uds_response(data):
    """Parse UDS response correctly"""
    if not data or len(data) < 2:
        return None, "Invalid data"

    # First byte is message length (number of bytes including length byte)
    msg_length = data[0]

    # Check if we have a valid UDS message
    if msg_length + 1 != len(data):
        # Try alternative parsing
        pass

    # The actual UDS response starts at byte 1
    if len(data) < 2:
        return None, "Data too short"

    response_type = data[1]

    # Positive response for diagnostic session control
    if response_type == 0x50:
        return "SESSION_STARTED", data

    # Positive response for read data by identifier
    elif response_type == 0x62:
        if len(data) >= 5:
            # DID is in bytes 2-3, value in bytes 4-5
            did_high = data[2]
            did_low = data[3]
            did = (did_high << 8) | did_low
            value = (data[4] << 8) | data[5] if len(data) > 5 else 0
            return ("READ_DATA", did, value), data

    # Negative response
    elif response_type == 0x7F:
        error_code = data[2] if len(data) > 2 else 0
        return ("NEGATIVE", error_code), data

    # First frame for multi-frame
    elif (data[1] >> 4) == 0x1:
        return "MULTI_FRAME", data

    return None, data


def query_did(did_input):
    """Query a custom DID"""
    try:
        # Parse DID
        if isinstance(did_input, str):
            if did_input.startswith('0x'):
                did = int(did_input, 16)
            else:
                did = int(did_input, 16)
        else:
            did = did_input

        d_h = (did >> 8) & 0xFF
        d_l = did & 0xFF

        print(f"\n{'='*50}")
        print(f"Querying DID: 0x{did:04X}")
        print(f"{'='*50}")

        # Connect to CAN
        print(f"Connecting to {CHANNEL}...")
        bus = can.Bus(channel=CHANNEL, interface='socketcan', bitrate=BITRATE)

        # Send wake-up
        print("\n1. Sending wake-up...")
        send_cmd(bus, [0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
        response = receive_response(bus, timeout=0.3)
        if response:
            print(f"   Response: {response.hex().upper()}")
            result, _ = parse_uds_response(response)
            if result == "SESSION_STARTED":
                print("   ✅ Session started")
            else:
                print(f"   Response: {result}")
        else:
            print("   ⚠️  No wake-up response")

        time.sleep(0.05)

        # Send DID request
        print(f"\n2. Requesting DID 0x{did:04X}...")
        send_cmd(bus, [0x03, 0x22, d_h, d_l, 0x00, 0x00, 0x00, 0x00])

        # Receive response
        response = receive_response(bus, timeout=2.0)

        if response:
            print(f"\n3. Response received:")
            print(f"   Raw: {response.hex().upper()}")

            result, parsed = parse_uds_response(response)

            if result == "READ_DATA":
                _, resp_did, value = parsed
                print(f"   ✅ Read Data Response")
                print(f"   DID: 0x{resp_did:04X}")
                print(f"   Raw Value: {value} (0x{value:04X})")

                # Interpret based on DID
                if did == 0x220F:  # Voltage
                    voltage = value / 10.0
                    print(f"   📊 System Voltage: {voltage:.1f} V")

                elif did in [0x2210, 0x2211, 0x2212]:  # Axle Angles
                    if value >= 32768:
                        angle = (value - 65536) / 10.0
                    else:
                        angle = value / 10.0
                    names = {0x2210: "Axle 1",
                             0x2211: "Axle 5", 0x2212: "Axle 6"}
                    print(f"   📐 {names.get(did, 'Angle')}: {angle:.1f}°")

                elif did == 0x220D:  # Firmware
                    # For multi-frame, value might be incomplete
                    print(f"   🔧 Firmware data: {value:04X}")

                else:
                    # Generic display
                    print(f"   Value: {value}")
                    if value >= 32768:
                        print(f"   Signed: {value - 65536}")
                    print(f"   Hex: 0x{value:04X}")

            elif result == "SESSION_STARTED":
                print(f"   ✅ Session started")

            elif result == "NEGATIVE":
                error_code = parsed
                print(f"   ❌ Negative Response")
                errors = {
                    0x10: "General reject",
                    0x11: "Service not supported",
                    0x12: "Sub-function not supported",
                    0x22: "Conditions not correct",
                    0x31: "Request out of range",
                    0x33: "Security access denied",
                    0x78: "Response pending"
                }
                print(
                    f"   Error: {errors.get(error_code, f'0x{error_code:02X}')}")

            elif result == "MULTI_FRAME":
                print(f"   📦 Multi-frame response detected")
                print(f"   First frame: {response.hex().upper()}")
                # Parse first frame
                total_length = ((response[1] & 0x0F) << 8) | response[2]
                print(f"   Total length: {total_length} bytes")

                # Send flow control
                print(f"\n   Sending flow control...")
                send_cmd(bus, [0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

                # Collect consecutive frames
                all_data = bytearray(response[3:8])
                seq = 1
                start = time.time()

                while len(all_data) < total_length and time.time() - start < 2:
                    cf = receive_response(bus, timeout=0.5)
                    if cf and len(cf) >= 8:
                        frame_type = cf[1] >> 4 if len(cf) > 1 else 0
                        if frame_type == 0x2:  # Consecutive frame
                            print(f"   CF {seq}: {cf.hex().upper()}")
                            all_data.extend(cf[2:8])
                            seq += 1

                print(f"\n   Complete data ({len(all_data)} bytes):")
                print(f"   Hex: {all_data.hex().upper()}")

                # Try ASCII decode
                try:
                    ascii_str = all_data.decode(
                        'ascii', errors='ignore').strip('\x00')
                    if ascii_str:
                        print(f"   ASCII: {ascii_str}")
                except:
                    pass

                # For firmware version (0x220D)
                if did == 0x220D and len(all_data) >= 4:
                    print(
                        f"   Firmware: {all_data[0]}.{all_data[1]}.{all_data[2]}.{all_data[3]}")

            else:
                print(f"   ⚠️  Unknown response: {result}")

        else:
            print(f"\n   ❌ No response received (timeout)")

        bus.shutdown()
        print(f"\n✅ Bus shutdown complete")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def interactive_mode():
    """Interactive mode for testing multiple DIDs"""
    print("\n" + "="*50)
    print("CUSTOM DID TEST TOOL")
    print("="*50)
    print("\nEnter CAN DIDs to query (hex format)")
    print("Examples: 0x220F, 0x220D, 0xF190, 2210")
    print("Type 'quit' to exit\n")

    while True:
        did_input = input("DID > ").strip()

        if did_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break

        if not did_input:
            continue

        try:
            query_did(did_input)
        except Exception as e:
            print(f"Error: {e}")

        print("\n" + "-"*50)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query_did(sys.argv[1])
    else:
        interactive_mode()
