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
        """Establish CAN bus connection"""
        try:
            self.bus = can.interface.Bus(
                interface=self.config.interface,
                channel=self.config.channel,
                bitrate=self.config.bitrate
            )
            self._is_connected = True
            logger.info(f"CAN bus connected on {self.config.channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect CAN bus: {e}")
            return False
    
    def disconnect(self):
        """Shutdown CAN bus connection"""
        if self.bus:
            self.bus.shutdown()
            self._is_connected = False
            logger.info("CAN bus disconnected")
    
    def send_message(self, arbitration_id: int, data: bytes, is_extended: bool = True) -> bool:
        """Send CAN message"""
        if not self._is_connected:
            logger.error("CAN bus not connected")
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
            logger.error(f"Failed to send message: {e}")
            return False
    
    def receive_message(self, timeout: float = 1.0) -> Optional[can.Message]:
        """Receive CAN message with timeout"""
        if not self._is_connected:
            return None
        
        start = time.time()
        while time.time() - start < timeout:
            msg = self.bus.recv(0.01)
            if msg and msg.arbitration_id == self.config.rx_id:
                logger.debug(f"RX: {hex(msg.arbitration_id)} {msg.data.hex()}")
                return msg
        return None