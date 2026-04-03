#!/usr/bin/env python3
import asyncio
import signal
import sys
from config.settings import CANConfig, BLEConfig, SecurityConfig
from core.uds_client import UDSClient
from core.security_manager import SecurityManager
from ble.command_handler import CommandHandler
from ble.ble_server import UDSBLEServer
from utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


class UDSBLEBridge:
    """Main application class for UDS-CAN-BLE bridge"""

    def __init__(self):
        self.can_config = CANConfig()
        self.ble_config = BLEConfig()
        self.security_config = SecurityConfig()

        self.security_manager = SecurityManager(self.security_config)
        self.uds_client = UDSClient(self.can_config, self.security_manager)
        self.command_handler = CommandHandler(self.uds_client)
        self.ble_server = UDSBLEServer(self.ble_config, self.command_handler)

        self._running = False

    async def initialize(self) -> bool:
        """Initialize all components"""
        logger.info("Initializing UDS-BLE Bridge...")

        # Connect to ECU
        if not self.uds_client.connect():
            logger.error("Failed to connect to ECU via CAN")
            return False

        logger.info("ECU connected successfully")

        # Start BLE server
        asyncio.create_task(self.ble_server.start())

        self._running = True
        return True

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down...")
        self._running = False

        self.uds_client.disconnect()

        # Stop BLE server
        if self.ble_server.server:
            await self.ble_server.server.stop()

        logger.info("Shutdown complete")

    async def run(self):
        """Main run loop"""
        try:
            if await self.initialize():
                logger.info("Bridge is running. Press Ctrl+C to stop.")

                # Keep running until interrupted
                while self._running:
                    await asyncio.sleep(1)
            else:
                logger.error("Failed to initialize bridge")

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.shutdown()


def main():
    """Entry point"""
    # Setup logging
    setup_logger(level="INFO")

    # Create and run bridge
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
