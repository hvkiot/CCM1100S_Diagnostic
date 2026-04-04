# /ble/ble_server.py
import asyncio
import json
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property, signal
from dbus_next.constants import PropertyAccess, BusType
from dbus_next import Variant
from utils.logger import get_logger

logger = get_logger(__name__)

SERVICE_UUID = "12345678-1234-1234-1234-123456789ABC"
CHARACTERISTIC_UUID = "87654321-4321-4321-4321-CBA987654321"


class GATTCharacteristic(ServiceInterface):
    def __init__(self, index, uuid, flags, service_path, command_handler):
        super().__init__('org.bluez.GattCharacteristic1')
        self.path = f"{service_path}/char{index}"
        self.uuid = uuid
        self.flags = flags
        self.service_path = service_path
        self.command_handler = command_handler
        self.notifying = False

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> 'o':
        return self.service_path

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> 'as':
        return self.flags

    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        return []

    @method()
    async def WriteValue(self, value: 'ay', options: 'a{sv}'):
        """Handle write from Flutter app"""
        try:
            data = bytes(value)
            decoded = data.decode('utf-8')
            message = json.loads(decoded)
            logger.info(f"📥 Received: {message.get('command')}")

            # Process command and send response
            asyncio.create_task(self._send_response(message))

        except Exception as e:
            logger.error(f"Write error: {e}")

    @method()
    async def StartNotify(self):
        self.notifying = True
        logger.info("Notifications enabled")

    @method()
    async def StopNotify(self):
        self.notifying = False
        logger.info("Notifications disabled")

    @signal()
    def Notify(self, value: 'ay') -> 'ay':
        return value

    async def _send_response(self, message):
        """Process command and send response via notification"""
        try:
            response = await self.command_handler.handle_command(message)
            logger.info(f"Response: {response}")

            if self.notifying:
                response_json = json.dumps(response)
                response_bytes = list(response_json.encode('utf-8'))
                self.Notify(response_bytes)
                logger.info("✅ Notification sent")
            else:
                logger.warning("Notifications disabled")

        except Exception as e:
            logger.error(f"Response error: {e}")


class GATTService(ServiceInterface):
    def __init__(self, index, uuid, primary):
        super().__init__('org.bluez.GattService1')
        self.path = f"/org/bluez/app/service{index}"
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> 'b':
        return self.primary

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)


class GATTApplication(ServiceInterface):
    def __init__(self):
        super().__init__('org.freedesktop.DBus.ObjectManager')
        self.path = "/org/bluez/app"
        self.services = []

    def add_service(self, service):
        self.services.append(service)

    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        response = {}
        for service in self.services:
            response[service.path] = {
                'org.bluez.GattService1': {
                    'UUID': Variant('s', service.uuid),
                    'Primary': Variant('b', service.primary)
                }
            }
            for char in service.characteristics:
                response[char.path] = {
                    'org.bluez.GattCharacteristic1': {
                        'UUID': Variant('s', char.uuid),
                        'Service': Variant('o', service.path),
                        'Flags': Variant('as', char.flags)
                    }
                }
        return response


class BLEServer:
    def __init__(self, command_handler):
        self.command_handler = command_handler
        self.bus = None

    async def start(self):
        try:
            # Clean stale connections
            await self._clean_stale_connections()

            # Connect to system bus
            self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # Create application
            app = GATTApplication()
            service = GATTService(0, SERVICE_UUID, True)
            characteristic = GATTCharacteristic(
                0, CHARACTERISTIC_UUID,
                ['read', 'write', 'notify'],
                service.path,
                self.command_handler
            )

            service.add_characteristic(characteristic)
            app.add_service(service)

            # Export objects
            self.bus.export(app.path, app)
            self.bus.export(service.path, service)
            self.bus.export(characteristic.path, characteristic)

            # Register with BlueZ
            introspection = await self.bus.introspect('org.bluez', '/org/bluez/hci0')
            bluez = self.bus.get_proxy_object(
                'org.bluez', '/org/bluez/hci0', introspection)
            gatt_manager = bluez.get_interface('org.bluez.GattManager1')

            await gatt_manager.call_register_application(app.path, {})
            logger.info("✅ BLE server started successfully")

            # Keep running
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"BLE server error: {e}")
            raise

    async def _clean_stale_connections(self):
        try:
            import subprocess
            subprocess.run(['bluetoothctl', 'disconnect'], capture_output=True)
            logger.info("Cleaned stale connections")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

    async def stop(self):
        if self.bus:
            self.bus.disconnect()
            logger.info("BLE server stopped")
