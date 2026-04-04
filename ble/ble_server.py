# ble/ble_server.py
import asyncio
import json
import subprocess
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property, signal
from dbus_next.constants import PropertyAccess, BusType
from dbus_next import Variant
from utils.logger import get_logger
from config.settings import BLEConfig

logger = get_logger(__name__)

SERVICE_UUID = BLEConfig.service_uuid
CHARACTERISTIC_UUID = BLEConfig.characteristic_uuid


class Characteristic(ServiceInterface):
    def __init__(self, uuid, flags, service_path, command_handler):
        super().__init__('org.bluez.GattCharacteristic1')
        self.path = f"{service_path}/char0"
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
        return list(b'READY')

    @method()
    async def WriteValue(self, value: 'ay', options: 'a{sv}'):
        """Handle write from Flutter app"""
        try:
            data = bytes(value)
            message = json.loads(data.decode('utf-8'))
            logger.info(f"📥 Received: {message.get('command')}")

            # Return immediately to BlueZ - don't block
            # Start background task to handle ECU communication
            asyncio.create_task(self._execute_and_notify(message))

        except Exception as e:
            logger.error(f"Write error: {e}")

    async def _execute_and_notify(self, message):
        """Background task - talk to ECU, then notify phone"""
        try:
            # Small delay to ensure Android clears its write cache
            await asyncio.sleep(0.15)

            # Talk to ECU
            response = await self.command_handler.handle_command(message)

            # Another small delay before sending notification
            await asyncio.sleep(0.05)

            if self.notifying:
                response_json = json.dumps(response)
                # Convert to list of ints for dbus
                response_bytes = [b for b in response_json.encode('utf-8')]

                # Emit the signal
                self.Notify(response_bytes)
                logger.info(f"✅ ECU Response sent: {response_json}")
            else:
                logger.warning("Notifications disabled - response not sent")

        except Exception as e:
            logger.error(f"Background error: {e}")

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


class Service(ServiceInterface):
    def __init__(self, uuid, primary):
        super().__init__('org.bluez.GattService1')
        self.path = "/org/bluez/app/service0"
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> 'b':
        return self.primary

    def add_characteristic(self, char):
        self.characteristics.append(char)


class Application(ServiceInterface):
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


class Advertisement(ServiceInterface):
    def __init__(self):
        super().__init__('org.bluez.LEAdvertisement1')
        self.path = "/org/bluez/app/advertisement0"

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> 's':
        return 'peripheral'

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> 'as':
        return [SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> 's':
        return BLEConfig.device_name

    @method()
    def Release(self):
        logger.info("Advertisement released")


class BLEServer:
    def __init__(self, command_handler):
        self.command_handler = command_handler
        self.bus = None

    async def _force_disconnect_all(self):
        """Force disconnect any connected BLE devices"""
        try:
            # Get list of connected devices
            result = subprocess.run(['bluetoothctl', 'devices'],
                                    capture_output=True, text=True)
            devices = result.stdout

            for line in devices.split('\n'):
                if 'Device' in line:
                    addr = line.split(' ')[1]
                    # Disconnect each device
                    subprocess.run(['bluetoothctl', 'disconnect', addr],
                                   capture_output=True)
                    logger.info(f"Force disconnected: {addr}")

            # Also remove bonded devices
            subprocess.run(['bluetoothctl', 'remove'] + [addr for addr in devices if 'Device' in line],
                           capture_output=True)

            # Reset the adapter
            subprocess.run(['bluetoothctl', 'power', 'off'],
                           capture_output=True)
            subprocess.run(['bluetoothctl', 'power', 'on'],
                           capture_output=True)
            subprocess.run(['bluetoothctl', 'discoverable',
                           'on'], capture_output=True)
            subprocess.run(['bluetoothctl', 'pairable', 'on'],
                           capture_output=True)

            await asyncio.sleep(2)
            logger.info("BLE adapter reset and ready")

        except Exception as e:
            logger.warning(f"Force disconnect failed: {e}")

    async def start(self):
        try:
            # Force disconnect any existing connections
            await self._force_disconnect_all()

            # Connect to system bus
            self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # Create application
            app = Application()
            service = Service(SERVICE_UUID, True)
            characteristic = Characteristic(
                CHARACTERISTIC_UUID,
                ['read', 'write', 'indicate'],
                service.path,
                self.command_handler
            )
            advertisement = Advertisement()

            service.add_characteristic(characteristic)
            app.add_service(service)

            # Export objects
            self.bus.export(app.path, app)
            self.bus.export(service.path, service)
            self.bus.export(characteristic.path, characteristic)
            self.bus.export(advertisement.path, advertisement)

            # Get BlueZ interfaces
            introspection = await self.bus.introspect('org.bluez', '/org/bluez/hci0')
            bluez = self.bus.get_proxy_object(
                'org.bluez', '/org/bluez/hci0', introspection)

            # Register GATT application
            gatt_manager = bluez.get_interface('org.bluez.GattManager1')
            await gatt_manager.call_register_application(app.path, {})
            logger.info("✅ GATT application registered")

            # Register advertisement
            le_ad_manager = bluez.get_interface(
                'org.bluez.LEAdvertisingManager1')
            await le_ad_manager.call_register_advertisement(advertisement.path, {})
            logger.info(
                "✅ Advertisement registered - Device is now discoverable")

            logger.info("BLE server running. Ready for connections.")

            # Keep running
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"BLE server error: {e}")
            raise

    async def stop(self):
        if self.bus:
            self.bus.disconnect()
            logger.info("BLE server stopped")
