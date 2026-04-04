# /core/iso_tp.pyimport time
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)


class ISOTPHandler:
    """ISO-TP (ISO 15765-2) protocol handler - CORRECTED VERSION"""

    def __init__(self, can_sender, can_receiver):
        self.send_frame = can_sender
        self.recv_frame = can_receiver

    def _send_single_frame(self, payload: bytes) -> None:
        """Send Single Frame (SF) - PCI byte = 0x0N where N is length"""
        length = len(payload)
        # PCI byte: bits 7-4 = 0 (SF type), bits 3-0 = length
        # For UDS, the length includes the UDS service byte
        pci_byte = length & 0x0F
        frame = bytearray([pci_byte]) + payload
        # Pad to 8 bytes exactly
        while len(frame) < 8:
            frame.append(0x00)
        self.send_frame(bytes(frame))
        logger.info(f"TX SF: {frame.hex()}")  # Change to INFO to see in logs

    def _send_multi_frame(self, payload: bytes) -> bool:
        """Send multi-frame message (FF + CF)"""
        length = len(payload)

        # First Frame (FF) - PCI bytes: 0x10 + high nibble of length, then low byte
        ff_pci_byte1 = 0x10 | ((length >> 8) & 0x0F)
        ff_pci_byte2 = length & 0xFF
        frame = bytearray([ff_pci_byte1, ff_pci_byte2]) + payload[:6]
        while len(frame) < 8:
            frame.append(0x00)
        self.send_frame(bytes(frame))
        logger.debug(f"TX FF: {frame.hex()}")

        # Wait for Flow Control (FC) from ECU
        fc_data = self.recv_frame(1.0)
        if not fc_data:
            logger.error("No Flow Control received")
            return False

        fc_data = fc_data if isinstance(fc_data, bytes) else bytes(fc_data)
        fc_pci = (fc_data[0] >> 4) & 0x0F

        if fc_pci != 3:
            logger.error(f"Expected Flow Control (PCI=3), got {fc_pci}")
            return False

        # Parse FC parameters
        block_size = fc_data[1]
        st_min = fc_data[2]

        # Send Consecutive Frames (CF)
        seq_num = 1
        idx = 6  # Already sent first 6 bytes in FF

        while idx < length:
            # CF PCI byte: 0x20 + sequence number
            pci_byte = 0x20 | (seq_num & 0x0F)
            chunk = payload[idx:idx+7]
            frame = bytearray([pci_byte]) + chunk
            while len(frame) < 8:
                frame.append(0x00)
            self.send_frame(bytes(frame))
            logger.debug(f"TX CF (seq={seq_num}): {frame.hex()}")

            idx += 7
            seq_num = (seq_num + 1) & 0x0F

            # Apply Separation Time (STmin)
            if st_min < 0x80:
                time.sleep(st_min / 1000.0)
            elif st_min >= 0xF1 and st_min <= 0xF9:
                time.sleep((st_min - 0xF0) / 10000.0)

            # Check block size limit
            if block_size > 0 and (seq_num - 1) % block_size == 0 and idx < length:
                # Wait for next FC
                fc_data = self.recv_frame(1.0)
                if not fc_data:
                    logger.error("Timeout waiting for next FC")
                    return False
                fc_data = fc_data if isinstance(
                    fc_data, bytes) else bytes(fc_data)
                # Continue sending

        return True

    def send(self, payload: bytes, timeout: float = 2.0) -> Optional[bytes]:
        """Send UDS request and receive response"""
        length = len(payload)

        # Send request
        if length <= 7:
            self._send_single_frame(payload)
        else:
            if not self._send_multi_frame(payload):
                return None

        # Receive response
        return self._receive_response(timeout)

    def _receive_response(self, timeout: float = 2.0) -> Optional[bytes]:
        """Receive and parse UDS response"""
        start = time.time()

        while time.time() - start < timeout:
            msg = self.recv_frame(0.1)
            if msg is None:
                continue

            data = msg if isinstance(msg, bytes) else bytes(msg)
            logger.info(f"RX raw: {data.hex()}")  # Changed to INFO

            # Check if we have valid data
            if len(data) == 0 or data[0] == 0:
                logger.debug("Empty or zero frame, continuing...")
                continue

            pci_type = (data[0] >> 4) & 0x0F
            logger.info(f"PCI type: {pci_type}")

            # Single Frame (SF)
            if pci_type == 0:
                length = data[0] & 0x0F
                if length > 0 and length <= len(data) - 1:
                    response = data[1:1+length]
                    logger.info(f"RX SF response: {response.hex()}")
                    return bytes(response)
                else:
                    logger.warning(
                        f"Invalid SF length: {length}, data len: {len(data)}")
                    continue

            # First Frame (FF) - multi-frame response
            elif pci_type == 1:
                total_len = ((data[0] & 0x0F) << 8) | data[1]
                response = bytearray(data[2:8])  # First 6 bytes
                logger.info(
                    f"RX FF: total_len={total_len}, first={response.hex()}")

                # Send Flow Control (FC)
                fc = bytes([0x30, 0x00, 0x00, 0, 0, 0, 0, 0])
                self.send_frame(fc)
                logger.info(f"TX FC: {fc.hex()}")

                # Receive Consecutive Frames (CF)
                cf_timeout = time.time() + 2.0
                expected_seq = 1

                while len(response) < total_len and time.time() < cf_timeout:
                    cf_msg = self.recv_frame(0.5)
                    if cf_msg is None:
                        continue

                    cf_data = cf_msg if isinstance(
                        cf_msg, bytes) else bytes(cf_msg)
                    cf_pci = (cf_data[0] >> 4) & 0x0F

                    if cf_pci == 2:  # Consecutive Frame
                        seq_num = cf_data[0] & 0x0F
                        if seq_num != expected_seq:
                            logger.warning(
                                f"Sequence mismatch: expected {expected_seq}, got {seq_num}")

                        response.extend(cf_data[1:8])
                        expected_seq = (expected_seq + 1) & 0x0F
                        cf_timeout = time.time() + 2.0
                        logger.info(
                            f"RX CF (seq={seq_num}): total={len(response)}/{total_len}")
                    else:
                        logger.error(
                            f"Unexpected PCI type in response: {cf_pci}")
                        return None

                if len(response) >= total_len:
                    result = bytes(response[:total_len])
                    logger.info(
                        f"RX complete multi-frame response: {result.hex()}")
                    return result
                else:
                    logger.error(
                        f"Incomplete response: got {len(response)} of {total_len} bytes")
                    return None

        logger.error("Timeout waiting for response")
        return None
