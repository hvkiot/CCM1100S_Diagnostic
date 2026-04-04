# /core/iso_tp.py
import time
from typing import Optional, List
from dataclasses import dataclass


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
        """Send UDS message and receive response"""
        # Send request
        if not self._send_request(payload):
            return None

        # Receive response
        return self._receive_response(timeout)

    def _send_request(self, payload: bytes) -> bool:
        """Send UDS request with proper ISO-TP framing"""
        length = len(payload)

        # Single Frame (SF) - up to 7 bytes
        if length <= 7:
            data = bytearray([length]) + payload
            while len(data) < 8:
                data.append(0x00)
            self.send_frame(bytes(data))
            return True

        # Multi-frame (FF + CF) - more than 7 bytes
        first_len = min(6, length)

        # First Frame (FF)
        ff = bytearray([
            0x10 | ((length >> 8) & 0x0F),
            length & 0xFF
        ]) + payload[:first_len]
        while len(ff) < 8:
            ff.append(0x00)
        self.send_frame(bytes(ff))

        # Wait for Flow Control with longer timeout
        fc_data = self.recv_frame(1.0)
        if not fc_data or (fc_data[0] >> 4) != 3:
            logger.error("No Flow Control received")
            return False

        fc = FlowControl(block_size=fc_data[1], st_min=fc_data[2])

        # Send Consecutive Frames
        seq = 1
        idx = first_len

        while idx < length:
            chunk = payload[idx:idx+7]
            cf = bytearray([0x20 | (seq & 0x0F)]) + chunk
            while len(cf) < 8:
                cf.append(0x00)
            self.send_frame(bytes(cf))

            idx += len(chunk)
            seq = (seq + 1) % 16
            if fc.st_min_seconds > 0:
                time.sleep(fc.st_min_seconds)

        return True

    def _receive_response(self, timeout: float = 2.0) -> Optional[bytes]:
        """Receive and reassemble UDS response with proper timeout"""
        data = self.recv_frame(timeout)
        if not data:
            return None

        pci_type = data[0] >> 4

        # Single Frame (SF)
        if pci_type == 0:
            length = data[0] & 0x0F
            return data[1:1+length]

        # First Frame (FF) - multi-frame response
        elif pci_type == 1:
            total_len = ((data[0] & 0x0F) << 8) | data[1]
            response = bytearray(data[2:])

            # Send Flow Control (FC) - increase block size for faster transfer
            fc = bytes([0x30, 0x00, 0x64, 0, 0, 0, 0, 0])  # STmin=100ms
            self.send_frame(fc)

            # Collect Consecutive Frames (CF) with longer timeout
            last_received = time.time()
            while len(response) < total_len:
                cf = self.recv_frame(0.5)  # 500ms between frames
                if not cf:
                    if time.time() - last_received > 1.0:
                        logger.error(
                            "Timeout waiting for consecutive frames")
                        return None
                    continue

                last_received = time.time()
                cf_pci = cf[0] >> 4
                if cf_pci == 2:  # Consecutive Frame
                    response.extend(cf[1:])
                else:
                    logger.error(f"Unexpected PCI type: {cf_pci}")
                    return None

            return bytes(response[:total_len])

        return None
