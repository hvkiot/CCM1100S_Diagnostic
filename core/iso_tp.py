# /core/iso_tp.py
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ISOTPHandler:
    """ISO-TP (ISO 15765-2) protocol handler - matches working manual script"""

    def __init__(self, can_sender, can_receiver, tx_id=0x1BDA08F1, rx_id=0x1BDAF108):
        self.send_frame = can_sender
        self.recv_frame = can_receiver
        self.tx_id = tx_id
        self.rx_id = rx_id

    def send(self, payload: bytes, timeout: float = 2.0) -> Optional[bytes]:
        """Send UDS request and receive response"""
        # Send request (always 8 bytes with padding)
        request = bytearray([len(payload)]) + payload
        while len(request) < 8:
            request.append(0x00)
        self.send_frame(bytes(request))
        logger.debug(f"TX: {request.hex()}")

        # Receive response
        return self._receive_response(timeout)

    def _receive_response(self, timeout: float = 2.0) -> Optional[bytes]:
        """Receive and parse UDS response - handles both single and multi-frame"""
        start = time.time()
        response = bytearray()

        while time.time() - start < timeout:
            msg = self.recv_frame(0.1)
            if not msg:
                continue

            data = msg.data
            logger.debug(f"RX: {data.hex()}")

            pci_type = (data[0] >> 4) & 0x0F

            # Single Frame
            if pci_type == 0:
                length = data[0] & 0x0F
                response = data[1:1+length]
                return bytes(response)

            # First Frame of multi-frame
            elif pci_type == 1:
                total_len = ((data[0] & 0x0F) << 8) | data[1]
                response = bytearray(data[2:8])  # First 6 bytes of data

                # Send Flow Control
                fc = bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0])
                self.send_frame(fc)
                logger.debug(f"TX FC: {fc.hex()}")

                # Receive consecutive frames
                cf_timeout = time.time() + 1.0
                while len(response) < total_len and time.time() < cf_timeout:
                    cf_msg = self.recv_frame(0.5)
                    if not cf_msg:
                        continue

                    cf_data = cf_msg.data
                    cf_pci = (cf_data[0] >> 4) & 0x0F

                    if cf_pci == 2:  # Consecutive Frame
                        response.extend(cf_data[1:8])
                        cf_timeout = time.time() + 1.0  # Reset timeout on each frame
                    else:
                        logger.error(f"Unexpected PCI type: {cf_pci}")
                        return None

                return bytes(response[:total_len])

        return None
