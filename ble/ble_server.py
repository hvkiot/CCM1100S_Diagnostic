#!/usr/bin/env python3
import asyncio
import json
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property, signal
from dbus_next.constants import PropertyAccess, BusType
from dbus_next import Variant, DBusError
from utils.logger import get_logger

logger = get_logger(__name__)

SERVICE_UUID = "12345678-1234-1234-1234-123456789ABC"
CHARACTERISTIC_UUID = "87654321-4321-4321-4321-CBA987654321"


class UDSCharacteristic(ServiceInterface):
    """BLE Characteristic for UDS commands"""

    def __init__(self, command_handler):
        super().__init__(CHARACTERISTIC_UUID)
        self.command_handler = command_handler
        self.notifying = False

    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        """Handle read requests"""
        status = self.command_handler.get_status()
        return list(json.dumps(status).encode('utf-8'))

    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}'):
        """Handle write requests"""
        try:
            data = bytes(value)
            message = json.loads(data.decode('utf-8'))
            logger.info(f"Received command: {message.get('command')}")

            # Process command
            asyncio.create_task(self._process_command(message))

        except Exception as e:
            logger.error(f"Write error: {e}")

    @method()
    def StartNotify(self):
        """Start notifications"""
        self.notifying = True
        logger.info("Notifications started")

    @method()
    def StopNotify(self):
        """Stop notifications"""
        self.notifying = False
        logger.info("Notifications stopped")

    @signal()
    def Notify(self, value: 'ay'):
        """Send notification"""
        pass

    async def _process_command(self, message):
        """Process command and send notification"""
        try:
            response = await self.command_handler.handle_command(message)
            response_bytes = json.dumps(response).encode('utf-8')

            if self.notifying:
                self.Notify(list(response_bytes))

        except Exception as e:
            logger.error(f"Command processing error: {e}")


class UDSService(ServiceInterface):
    """Main UDS Service"""

    def __init__(self, command_handler):
        super().__init__(SERVICE_UUID)
        self.characteristic = UDSCharacteristic(command_handler)
        self.add_characteristic(self.characteristic)

    @dbus_property(access=PropertyAccess.READ)
    def DeviceName(self) -> 's':
        return "UDS-CAN-Bridge"


class BLEServer:
    """BLE Server using dbus-next"""

    def __init__(self, command_handler):
        self.command_handler = command_handler
        self.bus = None

    async def start(self):
        """Start BLE server"""
        try:
            # Connect to system bus
            self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # Get BlueZ service
            bluez = await self.bus.get_proxy_object(
                'org.bluez',
                '/org/bluez/hci0',
                'org.freedesktop.DBus.Introspectable'
            )

            # Create and register our service
            service = UDSService(self.command_handler)

            # Export the service
            await self.bus.export('/org/bluez/hci0/service0', service)

            logger.info("BLE server started successfully")
            logger.info(f"Service UUID: {SERVICE_UUID}")
            logger.info(f"Characteristic UUID: {CHARACTERISTIC_UUID}")

            # Keep running
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"BLE server error: {e}")
            raise

    async def stop(self):
        """Stop BLE server"""
        if self.bus:
            self.bus.disconnect()
            logger.info("BLE server stopped")
