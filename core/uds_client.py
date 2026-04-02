"""UDS (Unified Diagnostic Services) Client"""

import time
from typing import Tuple
from core.can_interface import CANInterface
from config.can_config import UDS_IDS, TIMEOUTS, UDS_COMMANDS
from core.decoder import decode_uds_response


class UDSClient:
    """UDS Protocol client for CCM1100S"""
    
    def __init__(self):
        self.can = CANInterface()
    
    def _send_flow_control(self):
        """Send flow control frame for multi-frame responses"""
        flow_control = can.Message(
            arbitration_id=UDS_IDS['request'],
            data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=True
        )
        self.can.send_message(
            arbitration_id=UDS_IDS['request'],
            data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        )
    
    def query_single_frame(self, did: int, timeout: float = TIMEOUTS['query']) -> Tuple[bool, str, str]:
        """Query single-frame UDS DID"""
        try:
            # Start diagnostic session
            self.can.start_diagnostic_session()
            time.sleep(TIMEOUTS['session_hold'])
            
            # Send request
            d_h, d_l = (did >> 8) & 0xFF, did & 0xFF
            self.can.send_message(
                arbitration_id=UDS_IDS['request'],
                data=[0x03, UDS_COMMANDS['read_data'], d_h, d_l, 0x00, 0x00, 0x00, 0x00]
            )
            
            # Wait for response
            start = time.time()
            while time.time() - start < timeout:
                msg = self.can.receive_message(0.1)
                
                if msg and msg.arbitration_id == UDS_IDS['response']:
                    data = msg.data
                    
                    # Check for negative response
                    if data[0] == UDS_COMMANDS['negative_response']:
                        return False, f"Negative response: 0x{data[2]:02X}", data.hex()
                    
                    frame_type = data[0] >> 4
                    if frame_type == 0x0:  # Single frame
                        length = data[0] & 0x0F
                        response_data = data[1:1+length]
                        decoded = decode_uds_response(response_data, did)
                        return True, decoded, data.hex()
            
            return False, "Timeout", ""
            
        except Exception as e:
            return False, f"Error: {e}", ""
    
    def query_multi_frame(self, did: int, timeout: float = TIMEOUTS['query']) -> Tuple[bool, str, str]:
        """Query multi-frame UDS DID"""
        try:
            self.can.start_diagnostic_session()
            time.sleep(TIMEOUTS['session_hold'])
            
            # Send request
            d_h, d_l = (did >> 8) & 0xFF, did & 0xFF
            self.can.send_message(
                arbitration_id=UDS_IDS['request'],
                data=[0x03, UDS_COMMANDS['read_data'], d_h, d_l, 0x00, 0x00, 0x00, 0x00]
            )
            
            # Wait for first frame
            start = time.time()
            first_frame = None
            
            while time.time() - start < timeout:
                msg = self.can.receive_message(0.1)
                if msg and msg.arbitration_id == UDS_IDS['response']:
                    data = msg.data
                    if (data[0] >> 4) == 0x1:  # First frame
                        first_frame = data
                        break
            
            if not first_frame:
                return False, "No first frame received", ""
            
            # Send flow control
            self._send_flow_control()
            
            # Parse first frame
            total_length = ((first_frame[0] & 0x0F) << 8) | first_frame[1]
            received_data = bytearray(first_frame[2:8])
            
            # Receive consecutive frames
            expected_seq = 1
            start = time.time()
            
            while len(received_data) < total_length and time.time() - start < timeout:
                msg = self.can.receive_message(0.1)
                if msg and msg.arbitration_id == UDS_IDS['response']:
                    data = msg.data
                    if (data[0] >> 4) == 0x2:  # Consecutive frame
                        seq = data[0] & 0x0F
                        if seq == expected_seq:
                            received_data.extend(data[1:8])
                            expected_seq = (expected_seq + 1) % 16
            
            if len(received_data) >= total_length:
                complete_data = bytes(received_data[:total_length])
                decoded = decode_uds_response(complete_data, did)
                return True, decoded, complete_data.hex()
            
            return False, f"Incomplete: {len(received_data)}/{total_length}", ""
            
        except Exception as e:
            return False, f"Error: {e}", ""