# /main.py
import asyncio
import signal
import sys
from config.settings import CANConfig, SecurityConfig
from core.uds_client import UDSClient
from core.security_manager import SecurityManager
from ble.command_handler import CommandHandler
from ble.ble_server import BLEServer
from utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


class UDSBLEBridge:
    def __init__(self):
        self.can_config = CANConfig()
        self.security_config = SecurityConfig()

        self.security_manager = SecurityManager(self.security_config)
        self.uds_client = UDSClient(self.can_config, self.security_manager)
        self.command_handler = CommandHandler(self.uds_client)
        self.ble_server = BLEServer(self.command_handler)

        self._running = False

    async def initialize(self) -> bool:
        logger.info("Initializing UDS-BLE Bridge...")

        # Connect to ECU
        if not self.uds_client.connect():
            logger.error("Failed to connect to ECU")
            return False

        logger.info("ECU connected")

        # Start BLE server
        asyncio.create_task(self.ble_server.start())

        self._running = True
        return True

    async def shutdown(self):
        logger.info("Shutting down...")
        self._running = False
        await self.ble_server.stop()
        self.uds_client.disconnect()
        logger.info("Shutdown complete")

    async def run(self):
        try:
            if await self.initialize():
                logger.info("Bridge running. Press Ctrl+C to stop")
                while self._running:
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted")
        finally:
            await self.shutdown()


def main():
    setup_logger(level="INFO")
    bridge = UDSBLEBridge()

    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
