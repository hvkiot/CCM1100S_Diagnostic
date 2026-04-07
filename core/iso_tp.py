import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ISOTPHandler:
    """ISO-TP (ISO 15765-2) protocol handler - 100% check.py Match"""

    def __init__(self, can_sender, can_receiver):
        self.send_frame = can_sender
        self.recv_frame = can_receiver

    def send(self, payload: bytes, timeout: float = 2.0) -> Optional[bytes]:
        """Send UDS request and receive response"""

        # 🛑 THE FIX: Non-Blocking Flush
        # Using 0.0 instantly clears ghost frames without adding an
        # artificial sleep delay that ruins the ECU's Security Timer!
        # while self.recv_frame(0.0) is not None:
        #     pass

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
        ff = bytearray([0x10 | ((length >> 8) & 0x0F),
                        length & 0xFF]) + payload[:first_len]

        while len(ff) < 8:
            ff.append(0x00)

        logger.debug(f"TX FF: {ff.hex()}")
        self.send_frame(bytes(ff))

        logger.info(f"Sent First Frame, waiting for Flow Control from ECU...")

        # Wait for Flow Control or Immediate Response
        fc_raw = self.recv_frame(1.0)
        if not fc_raw:
            logger.error("No Flow Control received (Timeout)")
            logger.error("ECU did not respond within 1 second")
            return False

        fc = bytes(fc_raw) if not isinstance(fc_raw, bytes) else fc_raw
        logger.debug(f"RX FC: {fc.hex()}")

        pci_type = (fc[0] >> 4) & 0x0F

        # 🔥 NEW: Handle Single Frame Response (Negative Response)
        if pci_type == 0:
            length = fc[0] & 0x0F
            response = bytes(fc[1:1+length])
            logger.error(
                f"ECU rejected request with immediate response: {response.hex()}")
            # This is a negative response (7F XX XX) - let _receive_response handle it
            return False

        # Handle Flow Control (Expected)
        elif pci_type == 3:
            stmin_raw = fc[2]
            if stmin_raw <= 0x7F:
                stmin = stmin_raw / 1000.0
            elif 0xF1 <= stmin_raw <= 0xF9:
                stmin = (stmin_raw - 0xF0) / 10000.0
            else:
                stmin = 0.01

            logger.debug(f"Using STmin: {stmin}s")

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
                time.sleep(stmin)

            return True

        else:
            logger.error(
                f"Unexpected PCI type {pci_type} received: {fc.hex()}")
            return False

    def _receive_response(self, timeout: float = 2.0) -> Optional[bytes]:
        """Receive and parse UDS response (Strict Match to check.py)"""
        start = time.time()

        while time.time() - start < timeout:
            data = self.recv_frame(0.1)
            if data is None:
                continue

            raw = bytes(data) if not isinstance(data, bytes) else data
            logger.debug(f"RX raw frame: {raw.hex()}")
            pci_type = (raw[0] >> 4) & 0x0F

            # Single Frame (SF)
            if pci_type == 0:
                length = raw[0] & 0x0F
                return bytes(raw[1:1+length])

            # First Frame (FF)
            elif pci_type == 1:
                total_len = ((raw[0] & 0x0F) << 8) | raw[1]
                response = bytearray(raw[2:8])

                # 🛑 CRITICAL: Send Flow Control IMMEDIATELY
                # This explicitly matches check.py to keep the ECU happy.
                fc = bytes([0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
                self.send_frame(fc)

                # Receive Consecutive Frames
                cf_timeout = time.time() + 1.0
                while len(response) < total_len and time.time() < cf_timeout:
                    cf_raw = self.recv_frame(0.5)
                    if cf_raw is None:
                        continue

                    cf_data = bytes(cf_raw) if not isinstance(
                        cf_raw, bytes) else cf_raw
                    cf_pci = (cf_data[0] >> 4) & 0x0F

                    if cf_pci == 2:  # Consecutive Frame
                        response.extend(cf_data[1:8])
                        cf_timeout = time.time() + 1.0  # Reset timeout
                    else:
                        logger.warning(f"Unknown PCI type: {cf_pci}")
                        continue

                if len(response) >= total_len:
                    result = bytes(response[:total_len])
                    time.sleep(0.05)
                    return result
                else:
                    logger.error(
                        f"Incomplete: got {len(response)} of {total_len}")
                    return None
            else:
                continue

        logger.error("Timeout waiting for response")
        return None
