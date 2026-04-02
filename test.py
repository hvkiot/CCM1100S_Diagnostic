import can
import isotp
import udsoncan
from udsoncan.client import Client
# Fixed Import Path:
from udsoncan.connections import PythonCanIsotpConnection

# --- CAN BUS SETUP ---
bus = can.interface.Bus(interface='socketcan', channel='can1', bitrate=250000)

# --- ISO-TP ADDRESSING ---
# Using 29-bit extended IDs as per your successful terminal tests
tp_addr = isotp.Address(
    txid=0x1BDA08F1, 
    rxid=0x1BDAF108, 
    addressing_mode=isotp.AddressingMode.Normal_29bits
)

# --- UDS CONNECTION ---
# This links the CAN bus and the ISO-TP addressing into one object
conn = PythonCanIsotpConnection(bus, address=tp_addr)

# --- CLIENT CONFIG ---
# This prevents the 'timeout' TypeError from your previous run
client_config = {
    'request_timeout': 2.0,
    'p2_timeout': 1.0,
    'p2_star_timeout': 5.0,
    'standard_version': 2020 # Adjust based on your ECU's age
}

# --- EXECUTION ---
with Client(conn, config=client_config) as client:
    try:
        # Query HW Number (0xF191)
        response = client.read_data_by_identifier(0xF191)
        
        # In udsoncan, response.data contains the payload 
        # (the bytes after the Service and DID)
        if response.positive:
            hw_hex = response.data.hex().upper()
            hw_str = response.data.decode('ascii', errors='ignore').strip()
            print(f"✅ Success!")
            print(f"Raw Hex: {hw_hex}")
            print(f"ASCII String: {hw_str}")
        else:
            print(f"❌ ECU returned a Negative Response: {response.code_name}")

    except Exception as e:
        print(f"⚠️ An error occurred: {e}")

# Ensure the bus is closed if the script finishes
bus.shutdown()