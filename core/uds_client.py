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

    def _send_can_frame(self, data: bytes):
        """Send CAN frame via CAN manager"""
        self.can_manager.send_message(
            self.can_manager.config.tx_id,  # 0x1BDA08F1
            data
        )

    def _receive_can_frame(self, timeout: float = 1.0):
        """Receive CAN frame via CAN manager"""
        msg = self.can_manager.receive_message(timeout)
        return msg.data if msg else None

    def connect(self) -> bool:
        """Establish connection to ECU"""
        if not self.can_manager.connect():
            return False

        self.iso_tp = ISOTPHandler(
            can_sender=self._send_can_frame,
            can_receiver=self._receive_can_frame,
            tx_id=self.can_manager.config.tx_id,
            rx_id=self.can_manager.config.rx_id
        )

        # Try to switch to extended session
        try:
            return self._diagnostic_session_control(UDSSessionType.EXTENDED)
        except Exception as e:
            logger.warning(f"Session control failed: {e}")
            return False
