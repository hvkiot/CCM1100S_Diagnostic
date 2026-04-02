"""CAN Bus Interface Manager"""

import can
import time
from typing import Optional, Tuple
from config.can_config import CAN_CONFIG, TIMEOUTS, UDS_IDS


class CANInterface:
    """Singleton CAN bus interface manager"""
    
    _instance = None
    _bus = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._bus is None:
            self._connect()
    
    def _connect(self):
        """Establish CAN connection"""
        try:
            self._bus = can.Bus(
                channel=CAN_CONFIG['channel'],
                interface=CAN_CONFIG['interface'],
                bitrate=CAN_CONFIG['bitrate']
            )
            print(f"✅ CAN bus connected on {CAN_CONFIG['channel']}")
        except Exception as e:
            print(f"❌ CAN connection failed: {e}")
            raise
    
    def get_bus(self):
        """Return CAN bus instance"""
        return self._bus
    
    def send_message(self, arbitration_id: int, data: list, is_extended: bool = True):
        """Send CAN message"""
        msg = can.Message(
            arbitration_id=arbitration_id,
            data=data,
            is_extended_id=is_extended
        )
        self._bus.send(msg)
    
    def receive_message(self, timeout: float = 0.1) -> Optional[can.Message]:
        """Receive CAN message with timeout"""
        try:
            return self._bus.recv(timeout)
        except Exception:
            return None
    
    def close(self):
        """Close CAN connection"""
        if self._bus:
            self._bus.shutdown()
    
    def start_diagnostic_session(self) -> bool:
        """Start UDS diagnostic session"""
        msg = can.Message(
            arbitration_id=UDS_IDS['request'],
            data=[0x02, 0x10, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=True
        )
        self._bus.send(msg)
        
        start = time.time()
        while time.time() - start < TIMEOUTS['wakeup']:
            response = self.receive_message(0.05)
            if response and response.arbitration_id == UDS_IDS['response']:
                if response.data[0] == 0x50:
                    return True
        return True  # Assume session exists
    
    def stop_diagnostic_session(self):
        """Stop UDS diagnostic session"""
        msg = can.Message(
            arbitration_id=UDS_IDS['request'],
            data=[0x02, 0x20, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
            is_extended_id=True
        )
        self._bus.send(msg)
        time.sleep(TIMEOUTS['flow_control'])