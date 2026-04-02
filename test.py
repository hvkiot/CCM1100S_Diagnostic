# custom_did_test.py
import can
import time

# Configuration
CHANNEL = 'can1'
BITRATE = 250000
REQUEST_ID = 0x1BDA08F1
RESPONSE_ID = 0x1BDAF108

def send_cmd(bus, data):
    """Send CAN command"""
    msg = can.Message(
        arbitration_id=REQUEST_ID,
        data=data,
        is_extended_id=True
    )
    bus.send(msg)
    print(f"  Sent: {data.hex().upper()}")

def receive_response(bus, timeout=1.5):
    """Receive CAN response"""
    start = time.time()
    while time.time() - start < timeout:
        msg = bus.recv(timeout=0.1)
        if msg and msg.arbitration_id == RESPONSE_ID:
            return msg.data
    return None

def query_did(did_hex):
    """Query a custom DID"""
    try:
        # Parse DID
        if did_hex.startswith('0x'):
            did = int(did_hex, 16)
        else:
            did = int(did_hex, 16)
        
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
        
        time.sleep(0.05)
        
        # Send DID request
        print(f"\n2. Requesting DID 0x{did:04X}...")
        send_cmd(bus, [0x03, 0x22, d_h, d_l, 0x00, 0x00, 0x00, 0x00])
        
        # Receive response
        response = receive_response(bus, timeout=2.0)
        
        if response:
            print(f"\n3. Response received:")
            print(f"   Raw: {response.hex().upper()}")
            
            # Parse response
            first_byte = response[0]
            
            if first_byte == 0x50:
                print(f"   ✅ Session started")
                
            elif first_byte == 0x62:
                print(f"   ✅ Positive response")
                if len(response) >= 5:
                    value = (response[3] << 8) | response[4]
                    print(f"   Value: {value} (0x{value:04X})")
                    
                    # Try to interpret as different types
                    print(f"\n   Interpretations:")
                    print(f"   - As raw: {value}")
                    if value >= 32768:
                        signed = value - 65536
                        print(f"   - As signed: {signed}")
                    print(f"   - As voltage: {value / 10.0:.1f} V")
                    print(f"   - As angle: {value / 10.0:.1f}°")
                    print(f"   - As current: {value - 32000} mA")
                    
            elif first_byte == 0x10:
                print(f"   📦 Multi-frame response (First Frame)")
                total_len = ((response[0] & 0x0F) << 8) | response[1]
                print(f"   Total length: {total_len} bytes")
                print(f"   First data: {response[2:8].hex().upper()}")
                
                # Send flow control
                print(f"\n   Sending flow control...")
                send_cmd(bus, [0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                
                # Collect all frames
                all_data = bytearray(response[2:8])
                seq = 1
                start = time.time()
                
                while len(all_data) < total_len and time.time() - start < 2:
                    cf = receive_response(bus, timeout=0.5)
                    if cf and (cf[0] >> 4) == 0x2:
                        print(f"   Consecutive frame {seq}: {cf.hex().upper()}")
                        all_data.extend(cf[1:8])
                        seq += 1
                
                print(f"\n   Complete data ({len(all_data)} bytes): {all_data.hex().upper()}")
                
                # Try to decode as ASCII if printable
                try:
                    ascii_str = all_data.decode('ascii', errors='ignore').strip('\x00')
                    if ascii_str and all(32 <= ord(c) < 127 for c in ascii_str):
                        print(f"   ASCII: {ascii_str}")
                except:
                    pass
                
            elif first_byte == 0x7F:
                error_code = response[2] if len(response) > 2 else 0
                print(f"   ❌ Negative response")
                print(f"   Error code: 0x{error_code:02X}")
                errors = {
                    0x10: "General reject",
                    0x11: "Service not supported",
                    0x22: "Conditions not correct",
                    0x31: "Request out of range",
                    0x33: "Security access denied",
                    0x78: "Response pending"
                }
                print(f"   Meaning: {errors.get(error_code, 'Unknown')}")
            
            else:
                print(f"   ⚠️  Unknown response type")
        
        else:
            print(f"\n   ❌ No response received (timeout)")
        
        bus.shutdown()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

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

def batch_mode(did_list):
    """Test multiple DIDs in batch"""
    print("\n" + "="*50)
    print("BATCH TEST MODE")
    print("="*50)
    
    for did in did_list:
        query_did(did)
        time.sleep(0.5)
        print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == '--batch':
            # Batch test common DIDs
            batch_mode(['0x220F', '0x220D', '0x2210', '0x2211', '0x2212'])
        else:
            # Single DID from command line
            query_did(sys.argv[1])
    else:
        # Interactive mode
        interactive_mode()