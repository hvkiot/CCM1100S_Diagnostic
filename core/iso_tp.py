import time
from typing import Optional, List
from dataclasses import dataclass
import struct

@dataclass
class FlowControl:
    block_size: int
    st_min: int
    
    @property
    def st_min_seconds(self) -> float:
        if self.st_min <= 0x7F:
            return self.st_min / 1000.0
        elif 0xF1 <= self.st_min <= 0xF9:
            return (self.st_min - 0xF0) / 10000.0
        return 0.0

class ISOTPHandler:
    """ISO-TP (ISO 15765-2) protocol handler"""
    
    def __init__(self, can_sender, can_receiver):
        self.send_frame = can_sender
        self.recv_frame = can_receiver
        self.default_flow_control = FlowControl(block_size=0, st_min=0)
    
    def send(self, payload: bytes, timeout: float = 1.0) -> Optional[bytes]:
        """Send UDS message with automatic multi-frame handling"""
        length = len(payload)
        
        # Single Frame (SF)
        if length <= 7:
            return self._send_single_frame(payload, timeout)
        
        # Multi-frame (FF + CF)
        return self._send_multi_frame(payload, timeout)
    
    def _send_single_frame(self, payload: bytes, timeout: float) -> Optional[bytes]:
        """Send single frame message"""
        data = bytes([len(payload)]) + payload + bytes(7 - len(payload))
        self.send_frame(data)
        return self._receive_response(timeout)
    
    def _send_multi_frame(self, payload: bytes, timeout: float) -> Optional[bytes]:
        """Send multi-frame message with flow control"""
        first_len = min(6, len(payload))
        
        # First Frame (FF)
        ff = bytes([
            0x10 | ((len(payload) >> 8) & 0x0F),
            len(payload) & 0xFF
        ]) + payload[:first_len]
        ff += bytes(8 - len(ff))
        self.send_frame(ff)
        
        # Wait for Flow Control
        fc_data = self.recv_frame(timeout)
        if not fc_data or (fc_data[0] >> 4) != 3:
            print("No Flow Control received")
            return None
        
        fc = FlowControl(block_size=fc_data[1], st_min=fc_data[2])
        
        # Send Consecutive Frames
        seq = 1
        idx = first_len
        
        while idx < len(payload):
            chunk = payload[idx:idx+7]
            cf = bytes([0x20 | (seq & 0x0F)]) + chunk
            cf += bytes(8 - len(cf))
            self.send_frame(cf)
            
            idx += len(chunk)
            seq = (seq + 1) % 16
            time.sleep(fc.st_min_seconds)
        
        return self._receive_response(timeout)
    
    def receive(self, timeout: float = 1.0) -> Optional[bytes]:
        """Receive and reassemble UDS message"""
        data = self.recv_frame(timeout)
        if not data:
            return None
        
        pci_type = data[0] >> 4
        
        # Single Frame
        if pci_type == 0:
            length = data[0] & 0x0F
            return data[1:1+length]
        
        # First Frame (multi-frame)
        elif pci_type == 1:
            total_len = ((data[0] & 0x0F) << 8) | data[1]
            response = data[2:]
            
            # Send Flow Control
            fc = bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0])
            self.send_frame(fc)
            
            # Collect Consecutive Frames
            while len(response) < total_len:
                cf = self.recv_frame(timeout)
                if not cf or (cf[0] >> 4) != 2:
                    return None
                response += cf[1:]
            
            return response[:total_len]
        
        return None
    
    def _receive_response(self, timeout: float) -> Optional[bytes]:
        """Helper to receive and process response"""
        return self.receive(timeout)