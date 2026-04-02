"""J1939 Protocol Parser for Real-time Data"""

import can
from typing import Dict, Any
from core.can_interface import CANInterface
from config.did_config import J1939_MAPPING


class J1939Parser:
    """Parser for J1939 broadcast messages"""
    
    def __init__(self):
        self.can = CANInterface()
        self._listener_active = False
        self._latest_data = {}
    
    def parse_message(self, arbitration_id: int, data: bytes) -> Dict[str, Any]:
        """Parse J1939 message based on ID"""
        result = {}
        
        if arbitration_id in J1939_MAPPING:
            mapping = J1939_MAPPING[arbitration_id]
            
            for item in mapping['data']:
                value = self._extract_value(data, item['start'], item['bits'])
                
                if 'resolution' in item and 'offset' in item:
                    value = value * item['resolution'] + item['offset']
                    value = round(value, 2)
                
                if 'solenoid_states' in mapping:
                    state_map = mapping['solenoid_states']
                    value = state_map.get(value, f"UNKNOWN({value})")
                
                result[item['name']] = value
        
        return result
    
    def _extract_value(self, data: bytes, start_bit: int, bits: int) -> int:
        """Extract value from CAN data at specific bit position"""
        byte_start = start_bit // 8
        bit_offset = start_bit % 8
        
        if byte_start + ((bits + bit_offset - 1) // 8) >= len(data):
            return 0
        
        value = 0
        for i in range(bits):
            byte_idx = byte_start + (bit_offset + i) // 8
            bit_pos = 7 - ((bit_offset + i) % 8)
            if (data[byte_idx] >> bit_pos) & 1:
                value |= (1 << (bits - 1 - i))
        
        return value
    
    def get_realtime_data(self, timeout: float = 1.0) -> Dict[str, Any]:
        """Get latest real-time data from broadcast messages"""
        result = {}
        start = time.time()
        
        while time.time() - start < timeout:
            msg = self.can.receive_message(0.05)
            if msg:
                parsed = self.parse_message(msg.arbitration_id, msg.data)
                result.update(parsed)
                self._latest_data.update(parsed)
        
        return result
    
    def start_listener(self, callback):
        """Start background listener for real-time data"""
        import threading
        
        def listen_loop():
            self._listener_active = True
            while self._listener_active:
                msg = self.can.receive_message(0.1)
                if msg:
                    parsed = self.parse_message(msg.arbitration_id, msg.data)
                    if parsed and callback:
                        callback(parsed)
        
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()
        return thread
    
    def stop_listener(self):
        """Stop background listener"""
        self._listener_active = False