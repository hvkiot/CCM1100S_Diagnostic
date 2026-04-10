# core/can_bus.py
import can
from typing import Optional
from config.settings import CANConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class CANBusManager:
    """Manager for CAN bus operations"""

    def __init__(self, config: CANConfig):
        self.config = config
        self.bus: Optional[can.interface.Bus] = None
        self._is_connected = False

    def connect(self) -> bool:
        try:
            self.disconnect()
            self.bus = can.interface.Bus(
                interface=self.config.interface,
                channel=self.config.channel,
                bitrate=self.config.bitrate,
                can_filters=[{
                    "can_id": self.config.rx_id,
                    "can_mask": 0x1FFFFFFF,
                    "extended": True
                }]
            )
            self._is_connected = True
            logger.info(
                f"CAN bus connected on {self.config.channel} with filter")
            return True
        except Exception as e:
            logger.error(f"Failed to connect CAN bus: {e}")
            return False

    def disconnect(self):
        """Shutdown CAN bus connection"""
        if self.bus:
            try:
                self.bus.shutdown()
            except:
                pass
            self.bus = None
            self._is_connected = False
            logger.info("CAN bus disconnected")

    def send_message(self, arbitration_id: int, data: bytes, is_extended: bool = True) -> bool:
        """Send CAN message with error handling"""
        if not self._is_connected or not self.bus:
            return False

        try:
            msg = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended
            )
            self.bus.send(msg)
            logger.debug(f"TX: {hex(arbitration_id)} {data.hex()}")
            return True
        except Exception as e:
            error_msg = str(e)
            if "No buffer space available" in error_msg:
                # 🛑 KEEP THE SOCKET OPEN! 
                # ECU is likely OFF. We drop the packet and wait for ECU to come online.
                # The CAN controller will empty the queue when the ECU responds.
                pass
            elif "Network is down" in error_msg:
                self._is_connected = False
            else:
                logger.error(f"Failed to send message: {e}")
            return False

    def receive_message(self, timeout: float = 1.0) -> Optional[can.Message]:
        """Receive CAN message"""
        if not self._is_connected or not self.bus:
            return None

        try:
            msg = self.bus.recv(timeout)
            if msg:
                logger.debug(f"RX: {hex(msg.arbitration_id)} {msg.data.hex()}")
                return msg
        except Exception as e:
            pass
        return None

    @property
    def is_connected(self) -> bool:
        return self._is_connected
