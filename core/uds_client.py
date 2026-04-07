# /core/uds_client.py
from typing import Optional
from enum import Enum
import time
from core.can_bus import CANBusManager
from core.iso_tp import ISOTPHandler
from core.security_manager import SecurityManager
from config.settings import CANConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class UDSSessionType(Enum):
    DEFAULT = 0x01
    PROGRAMMING = 0x02
    EXTENDED = 0x03


class UDSClient:
    """UDS (ISO 14229) client implementation"""

    def __init__(self, can_config: CANConfig, security_manager: SecurityManager):
        self.can_manager = CANBusManager(can_config)
        self.security_manager = security_manager
        self.iso_tp = None
        self._is_authenticated = False
        self._current_session = UDSSessionType.DEFAULT

    def connect(self) -> bool:
        """Establish connection to ECU"""
        if not self.can_manager.connect():
            return False

        self.iso_tp = ISOTPHandler(
            can_sender=self._send_can_frame,
            can_receiver=self._receive_can_frame
        )

        # Try to switch to extended session
        try:
            return self.diagnostic_session_control(UDSSessionType.EXTENDED)
        except Exception as e:
            logger.warning(f"Session control failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from ECU"""
        self.can_manager.disconnect()
        self._is_authenticated = False

    def _send_can_frame(self, data: bytes):
        """Send CAN frame via CAN manager"""
        self.can_manager.send_message(
            self.can_manager.config.tx_id,
            data
        )

    def _receive_can_frame(self, timeout: float = 1.0):
        """Receive CAN frame"""
        msg = self.can_manager.receive_message(timeout)

        if msg and msg.arbitration_id == self.can_manager.config.rx_id:
            return msg.data
        return None

    def diagnostic_session_control(self, session_type: UDSSessionType) -> bool:
        """Switch diagnostic session"""
        response = self.raw_request(bytes([0x10, session_type.value]))
        if response and response[0] == 0x50:
            self._current_session = session_type
            logger.info(f"Switched to {session_type.name} session")
            return True
        return False

    def raw_request(self, payload: bytes, timeout: float = 1.0) -> Optional[bytes]:
        """Send raw UDS request"""
        if not self.iso_tp:
            return None
        response = self.iso_tp.send(payload, timeout)
        if response:
            logger.info(f"Raw response: {response.hex()}")
        return response

    def read_data_by_identifier(self, did: int) -> Optional[bytes]:
        """Read Data By Identifier (0x22) service with auto-scaling"""
        payload = bytes([0x22, (did >> 8) & 0xFF, did & 0xFF])
        logger.info(f"Sending Read DID 0x{did:04X}: payload={payload.hex()}")

        response = self.iso_tp.send(payload)

        if response and len(response) > 0 and response[0] == 0x62:
            # Skip 0x62 (1 byte) + DID (2 bytes) = 3 bytes total
            raw_data = response[3:]
            logger.info(
                f"Read DID 0x{did:04X} success, pure data: {raw_data.hex()}")

            # Scale the data based on DID
            scaled_data = self._scale_did_data(did, raw_data)
            return scaled_data

        elif response and response[0] == 0x7F:
            nrc = response[2] if len(response) > 2 else 0x00
            logger.error(f"Read DID failed: NRC 0x{nrc:02X}")
            return None

        logger.error(f"No response or invalid response for DID 0x{did:04X}")
        return None

    def _scale_did_data(self, did: int, data: bytes) -> bytes:
        """Scale raw hex data to human-readable format"""

        if all(b == 0 for b in data):
            return "Not Programmed".encode('utf-8')

        # ASCII Strings (return as-is)
        if did in [0xF190, 0xF191, 0xF187, 0xF188, 0xF1A0, 0xF1A1, 0xF1A6, 0x220D, 0x220E]:
            return data  # Already ASCII

        # 32-bit Unsigned Integer (Serial Number, Product Code)
        elif did in [0xF18C, 0xF192]:
            if len(data) >= 4:
                value = int.from_bytes(data[:4], byteorder='big')
                return str(value).encode('utf-8')

        # System Voltage (0.1V resolution)
        elif did == 0x220F:
            if len(data) >= 2:
                raw = int.from_bytes(data[:2], byteorder='big')
                voltage = raw / 10.0
                return f"{voltage:.1f}V".encode('utf-8')

        # Axle Angles (signed, 0.1 degree resolution)
        elif did in [0x2210, 0x2211, 0x2212]:
            if len(data) >= 2:
                raw = int.from_bytes(data[:2], byteorder='big', signed=True)
                angle = raw / 10.0
                return f"{angle:.1f}°".encode('utf-8')

        # Axle Control Percentages (signed, 1% resolution)
        elif did in [0x2213, 0x2214]:
            if len(data) >= 2:
                percentage = int.from_bytes(
                    data[:2], byteorder='big', signed=True)
                return f"{percentage}%".encode('utf-8')

        # Min/Max Axle Currents (signed, 1mA resolution)
        elif did in [0x2215, 0x2216, 0x2217, 0x2218, 0x2219, 0x221A, 0x221B, 0x221C]:
            if len(data) >= 2:
                current = int.from_bytes(
                    data[:2], byteorder='big', signed=True)
                return f"{current}mA".encode('utf-8')

        # Default: return raw hex as string
        return data.hex().encode('utf-8')

    def write_data_by_identifier(self, did: int, data: bytes) -> bool:
        """Write Data By Identifier (0x2E) service"""

        logger.info(
            "Ensuring ECU is in Extended Session and unlocked before Write...")
        time.sleep(0.1)
        if not self.security_manager.do_security_access(self):
            logger.error("Failed to secure ECU for Write operation.")
            return False

        time.sleep(0.2)
        # Send the Write command IMMEDIATELY (Maximum Speed!)
        payload = bytes([0x2E, (did >> 8) & 0xFF, did & 0xFF]) + data

        logger.info(f"About to send write payload: {payload.hex()}")
        logger.info(f"Payload length: {len(payload)} bytes")
        logger.info(
            f"This will require {'Single Frame' if len(payload) <= 7 else 'Multi-frame'} transmission")

        response = self.iso_tp.send(payload)

        if response and response[0] == 0x6E:
            logger.info(f"Write DID 0x{did:04X} success")
            return True
        elif response and response[0] == 0x7F:
            nrc = response[2] if len(response) > 2 else 0x00
            logger.error(f"Write DID failed: NRC 0x{nrc:02X}")
            return False

        logger.error("Write DID failed: No valid response from ECU")
        return False

    def routine_control(self, routine_id: int, subfunction: int, data: bytes = b'') -> Optional[bytes]:
        """Routine Control (0x31) service"""
        payload = bytes([0x31, subfunction, (routine_id >> 8)
                        & 0xFF, routine_id & 0xFF]) + data
        return self.iso_tp.send(payload)
