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
        self._health_check_task = None

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

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except:
                pass

        if self.ble_server:
            await self.ble_server.stop()
        if self.uds_client:
            self.uds_client.disconnect()
        logger.info("Shutdown complete")

    async def health_check(self):
        """Background task to monitor ECU health"""
        while self._running:
            await asyncio.sleep(10)  # Check every 10 seconds

            if not self._running:
                break

            if self.uds_client and self.uds_client.can_manager._is_connected:
                try:
                    # Simple check - just see if we can send a tester present
                    # Don't wait too long
                    response = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None, self.uds_client.raw_request, bytes(
                                [0x3E, 0x00]), 0.3
                        ),
                        timeout=0.5
                    )
                    if response is None:
                        logger.warning(
                            "ECU not responding, will reconnect on next cycle")
                except asyncio.TimeoutError:
                    logger.warning("Health check timeout")
                except Exception as e:
                    logger.debug(f"Health check exception: {e}")

    async def run_forever(self):
        """Main loop with auto-restart on failure"""
        self._running = True

        while self._running:
            try:
                # Initialize connection
                if await self.initialize():
                    logger.info("Bridge running. Waiting for connections...")

                    # Start health check in background
                    self._health_check_task = asyncio.create_task(
                        self.health_check())

                    # Keep running until connection is lost
                    connection_lost = False
                    while self._running and not connection_lost:
                        await asyncio.sleep(2)

                        # Check if ECU is still connected
                        if self.uds_client and self.uds_client.can_manager._is_connected:
                            # Quick check without blocking
                            pass
                        else:
                            connection_lost = True
                            logger.warning("Connection lost")

                    # Cancel health check
                    if self._health_check_task:
                        self._health_check_task.cancel()
                        try:
                            await self._health_check_task
                        except:
                            pass
                        self._health_check_task = None

                    # Clean up
                    await self.shutdown()
                    logger.info("Waiting 3 seconds before reconnect...")
                    await asyncio.sleep(3)
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
