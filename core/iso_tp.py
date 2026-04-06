import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ISOTPHandler:
    """ISO-TP (ISO 15765-2) protocol handler - FIXED for multi-frame"""

    def __init__(self, can_sender, can_receiver):
        self.send_frame = can_sender
        self.recv_frame = can_receiver

    def send(self, payload: bytes, timeout: float = 2.0) -> Optional[bytes]:
        """Send UDS request and receive response"""
        # Send request
        if not self._send_request(payload):
            return None

        # Receive response
        return self._receive_response(timeout)

    def _send_request(self, payload: bytes) -> bool:
        """Send UDS request"""
        length = len(payload)

        # Single Frame (SF)
        if length <= 7:
            data = bytearray([length]) + payload
            while len(data) < 8:
                data.append(0x00)
            self.send_frame(bytes(data))
            return True

        # Multi-frame (FF + CF)
        first_len = min(6, length)

        # First Frame (FF)
        ff = bytearray([
            0x10 | ((length >> 8) & 0x0F),
            length & 0xFF
        ]) + payload[:first_len]
        while len(ff) < 8:
            ff.append(0x00)
        self.send_frame(bytes(ff))

        # Wait for Flow Control
        fc = self.recv_frame(0.5)
        if not fc or ((fc[0] >> 4) & 0x0F) != 3:
            logger.error("No Flow Control received")
            return False

        # Send Consecutive Frames
        seq = 1
        idx = first_len

        while idx < length:
            chunk = payload[idx:idx+7]
            cf = bytearray([0x20 | (seq & 0x0F)]) + chunk
            while len(cf) < 8:
                cf.append(0x00)
            self.send_frame(bytes(cf))
            idx += 7
            seq = (seq + 1) & 0x0F
            time.sleep(0.01)

        return True

    def _receive_response(self, timeout: float = 3.0) -> Optional[bytes]:
        """Receive and parse UDS response - handles multi-frame"""
        start = time.time()

        while time.time() - start < timeout:
            data = self.recv_frame(0.1)
            if data is None:
                continue

            # Convert to bytes if needed
            raw = bytes(data) if not isinstance(data, bytes) else data
            logger.debug(f"RX raw: {raw.hex()}")

            pci_type = (raw[0] >> 4) & 0x0F

            # Single Frame (SF)
            if pci_type == 0:
                length = raw[0] & 0x0F
                response = raw[1:1+length]
                logger.debug(f"RX SF: {response.hex()}")
                return bytes(response)

            # First Frame (FF) - Multi-frame
            elif pci_type == 1:
                total_len = ((raw[0] & 0x0F) << 8) | raw[1]
                response = bytearray(raw[2:8])  # First 6 bytes
                logger.info(
                    f"RX FF: total_len={total_len}, first={response.hex()}")

                # Send Flow Control
                fc = bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0])
                self.send_frame(fc)
                logger.debug(f"TX FC: {fc.hex()}")

                # Receive Consecutive Frames
                cf_timeout = time.time() + 2.0
                expected_seq = 1

                while len(response) < total_len and time.time() < cf_timeout:
                    cf_raw = self.recv_frame(0.5)
                    if cf_raw is None:
                        continue

                    cf_data = bytes(cf_raw) if not isinstance(
                        cf_raw, bytes) else cf_raw
                    cf_pci = (cf_data[0] >> 4) & 0x0F

                    if cf_pci == 2:  # Consecutive Frame
                        response.extend(cf_data[1:8])
                        expected_seq = (expected_seq + 1) & 0x0F
                        cf_timeout = time.time() + 2.0
                        logger.debug(
                            f"RX CF: total={len(response)}/{total_len}")
                    else:
                        logger.warning(f"Unexpected PCI: {cf_pci}")
                        continue

                if len(response) >= total_len:
                    result = bytes(response[:total_len])
                    logger.info(f"RX complete: {result.hex()}")
                    return result
                else:
                    logger.error(
                        f"Incomplete: got {len(response)} of {total_len}")
                    return None

            else:
                logger.warning(f"Unknown PCI type: {pci_type}")
                continue

        logger.error("Timeout waiting for response")
        return None
