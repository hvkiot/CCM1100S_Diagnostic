"""Data Decoder for UDS and J1939 Responses"""

from config.did_config import UDS_DIDS, DTC_CODES
from config.can_config import UDS_COMMANDS


def decode_uds_response(data: bytes, did: int) -> str:
    """Decode UDS response data"""
    try:
        if len(data) < 3:
            return f"Invalid: {data.hex()}"
        
        # Check for negative response
        if data[0] == UDS_COMMANDS['negative_response']:
            error_code = data[2] if len(data) > 2 else 0
            if error_code in DTC_CODES:
                return f"DTC: {DTC_CODES[error_code]}"
            return f"Error: 0x{error_code:02X}"
        
        # Positive response
        if data[0] != UDS_COMMANDS['positive_response']:
            return f"Unexpected: {data[0]:02X}"
        
        # Extract value data
        value_data = data[3:] if len(data) > 3 else b''
        
        if did in UDS_DIDS:
            info = UDS_DIDS[did]
            data_type = info.get('type', 'numeric')
            
            if data_type == 'version':
                if len(value_data) >= 4:
                    return f"{value_data[0]}.{value_data[1]}.{value_data[2]}.{value_data[3]}"
            
            elif data_type == 'ascii':
                ascii_str = value_data.decode('ascii', errors='ignore').strip('\x00')
                return ascii_str if ascii_str else "Not Programmed"
            
            elif data_type == 'uint32':
                if len(value_data) >= 4:
                    val = (value_data[0] << 24) | (value_data[1] << 16) | (value_data[2] << 8) | value_data[3]
                    return str(val)
            
            else:  # numeric
                if len(value_data) >= 2:
                    val = (value_data[0] << 8) | value_data[1]
                    if val >= 32768:
                        val -= 65536
                    
                    resolution = info.get('resolution', 1)
                    offset = info.get('offset', 0)
                    unit = info.get('unit', '')
                    
                    result = val * resolution + offset
                    return f"{result:.1f} {unit}".strip()
        
        return f"Hex: {value_data.hex(' ').upper()}"
    
    except Exception as e:
        return f"Decode error: {e}"


def decode_dtc(dtc_code: int) -> str:
    """Decode DTC error code"""
    return DTC_CODES.get(dtc_code, f"Unknown DTC: 0x{dtc_code:06X}")


def decode_solenoid_state(state: int) -> str:
    """Decode solenoid state (2-bit)"""
    states = {0: "OFF", 1: "ON", 2: "ERROR", 3: "NOT AVAILABLE"}
    return states.get(state, f"UNKNOWN({state})")