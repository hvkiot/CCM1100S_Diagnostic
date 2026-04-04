import asyncio
import signal
import sys
import time
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
        self.security_manager = None
        self.uds_client = None
        self.command_handler = None
        self.ble_server = None
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 0  # 0 means infinite

    async def initialize(self) -> bool:
        logger.info("Initializing UDS-BLE Bridge...")

        # Recreate objects each time
        self.security_manager = SecurityManager(self.security_config)
        self.uds_client = UDSClient(self.can_config, self.security_manager)
        self.command_handler = CommandHandler(self.uds_client)
        self.ble_server = BLEServer(self.command_handler)

        # Try to connect to ECU with retry
        retry_count = 0
        while retry_count < 3:
            if self.uds_client.connect():
                logger.info("ECU connected successfully")
                self._reconnect_attempts = 0
                return True
            retry_count += 1
            logger.warning(f"ECU connection failed, retry {retry_count}/3")
            await asyncio.sleep(2)

        logger.error("Failed to connect to ECU after retries")
        return False

    async def shutdown(self):
        logger.info("Shutting down...")
        self._running = False
        if self.ble_server:
            await self.ble_server.stop()
        if self.uds_client:
            self.uds_client.disconnect()
        logger.info("Shutdown complete")

    async def run_forever(self):
        """Main loop with auto-restart on failure"""
        self._running = True

        while self._running:
            try:
                # Initialize connection
                if await self.initialize():
                    logger.info("Bridge running. Monitoring connection...")

                    # Monitor connection health
                    while self._running:
                        await asyncio.sleep(5)

                        # Check if ECU is still responding
                        if self.uds_client and self.uds_client.can_manager._is_connected:
                            # Send a ping to check ECU health
                            try:
                                status = await asyncio.get_event_loop().run_in_executor(
                                    None, self.uds_client.raw_request, bytes(
                                        [0x3E, 0x00]), 0.5
                                )
                                if status is None:
                                    logger.warning(
                                        "ECU not responding, reconnecting...")
                                    break
                            except Exception as e:
                                logger.warning(
                                    f"Health check failed: {e}, reconnecting...")
                                break
                        else:
                            logger.warning("Connection lost, reconnecting...")
                            break
                else:
                    logger.error(
                        "Initialization failed, retrying in 5 seconds...")
                    await asyncio.sleep(5)
                    continue

                # If we get here, connection was lost - cleanup and retry
                logger.info("Cleaning up before retry...")
                await self.shutdown()
                await asyncio.sleep(3)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.exception(f"Unexpected error: {e}")
                await self.shutdown()
                await asyncio.sleep(5)

        await self.shutdown()

    async def run(self):
        """Legacy method for compatibility"""
        await self.run_forever()


def main():
    setup_logger(level="INFO")
    bridge = UDSBLEBridge()

    # Handle signals gracefully
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(bridge.run_forever())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
