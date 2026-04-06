# /core/uds_client.py
from typing import Optional, Dict, Any
from enum import Enum
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
        """Receive CAN frame via CAN manager"""
        msg = self.can_manager.receive_message(timeout)
        return msg.data if msg else None

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
        """Read Data By Identifier (0x22) service"""
        payload = bytes([0x22, (did >> 8) & 0xFF, did & 0xFF])
        logger.info(f"Sending Read DID 0x{did:04X}: payload={payload.hex()}")

        response = self.iso_tp.send(payload)

        if response:
            logger.info(f"Raw response: {response.hex()}")

        # Check for valid response - Response code 0x62 means success
        if response and len(response) > 0 and response[0] == 0x62:
            logger.info(
                f"Read DID 0x{did:04X} success, data length: {len(response)-1}")
            return response[1:]  # Return data without the 0x62 response code
        elif response and response[0] == 0x7F:
            nrc = response[2] if len(response) > 2 else 0x00
            logger.error(f"Read DID failed: NRC 0x{nrc:02X}")
            return None

        logger.error(f"No response or invalid response for DID 0x{did:04X}")
        return None

    def write_data_by_identifier(self, did: int, data: bytes) -> bool:
        """Write Data By Identifier (0x2E) service"""
        if not self._is_authenticated:
            logger.warning("Security access required for write operation")
            if not self.security_manager.do_security_access(self):
                return False
            self._is_authenticated = True

        payload = bytes([0x2E, (did >> 8) & 0xFF, did & 0xFF]) + data
        response = self.iso_tp.send(payload)

        if response and response[0] == 0x6E:
            logger.info(f"Write DID 0x{did:04X} success")
            return True
        elif response and response[0] == 0x7F:
            nrc = response[2]
            logger.error(f"Write DID failed: NRC 0x{nrc:02X}")
            return False

        return False

    def routine_control(self, routine_id: int, subfunction: int, data: bytes = b'') -> Optional[bytes]:
        """Routine Control (0x31) service"""
        payload = bytes([0x31, subfunction, (routine_id >> 8)
                        & 0xFF, routine_id & 0xFF]) + data
        return self.iso_tp.send(payload)
