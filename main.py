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
        self.security_manager = None
        self.uds_client = None
        self.command_handler = None
        self.ble_server = None
        self._running = False
        self._ble_task = None

    async def initialize(self) -> bool:
        logger.info("Initializing UDS-BLE Bridge...")

        # Recreate objects each time
        self.security_manager = SecurityManager(self.security_config)
        self.uds_client = UDSClient(self.can_config, self.security_manager)
        self.command_handler = CommandHandler(self.uds_client)
        self.ble_server = BLEServer(self.command_handler)

        # Try to connect to ECU
        for retry in range(3):
            if self.uds_client.connect():
                logger.info("ECU connected successfully")
                return True
            logger.warning(f"ECU connection failed, retry {retry + 1}/3")
            await asyncio.sleep(2)

        logger.error("Failed to connect to ECU after retries")
        return False

    async def shutdown(self):
        logger.info("Shutting down...")
        self._running = False

        if self._ble_task:
            self._ble_task.cancel()
            try:
                await self._ble_task
            except:
                pass

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
                    logger.info("Bridge running. Starting BLE server...")

                    # Start BLE server as a background task
                    self._ble_task = asyncio.create_task(
                        self.ble_server.start())

                    logger.info("Ready for BLE connections...")

                    # Keep running
                    while self._running:
                        await asyncio.sleep(1)
                else:
                    logger.error(
                        "Initialization failed, retrying in 5 seconds...")
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
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
        print(f"\nReceived signal {signum}, shutting down...")
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
