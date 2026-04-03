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


class LEAdvertisement(ServiceInterface):
    """LE Advertisement for device discovery"""

    def __init__(self):
        super().__init__('org.bluez.LEAdvertisement1')
        self.path = '/org/bluez/app/advertisement0'

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> 's':
        return 'peripheral'

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> 'as':
        return [SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> 's':
        return 'UDS-CAN-Bridge'

    @method()
    def Release(self):
        logger.info("Advertisement released")


class GATTCharacteristic(ServiceInterface):
    """Standard BlueZ GATT Characteristic"""

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
        """Handle read requests"""
        try:
            status = self.command_handler.get_status()
            return list(json.dumps(status).encode('utf-8'))
        except Exception as e:
            logger.error(f"ReadValue error: {e}")
            return []

    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}'):
        """Handle write requests"""
        try:
            data = bytes(value)
            message = json.loads(data.decode('utf-8'))
            logger.info(f"Received command: {message.get('command')}")
            asyncio.create_task(self._process_command(message))
        except Exception as e:
            logger.error(f"WriteValue error: {e}")

    @method()
    def StartNotify(self):
        self.notifying = True
        logger.info("Notifications started")

    @method()
    def StopNotify(self):
        self.notifying = False
        logger.info("Notifications stopped")

    @signal()
    def Notify(self, value: 'ay'):
        pass

    async def _process_command(self, message):
        """Process command and send notification"""
        try:
            logger.info(f"Processing command: {message.get('command')}")
            response = await self.command_handler.handle_command(message)
            logger.info(f"Got response: {response}")

            if self.notifying:
                response_bytes = json.dumps(response).encode('utf-8')
                logger.info(
                    f"Sending notification: {len(response_bytes)} bytes")
                logger.info(f"Response content: {response_bytes[:100]}")
                self.Notify(list(response_bytes))
                logger.info("Notification sent successfully")
            else:
                logger.warning("Cannot send response: notifying is False")

        except Exception as e:
            logger.error(f"Command processing error: {e}", exc_info=True)


class GATTService(ServiceInterface):
    """Standard BlueZ GATT Service"""

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
    """Application Root implementing ObjectManager for BlueZ"""

    def __init__(self):
        super().__init__('org.freedesktop.DBus.ObjectManager')
        self.path = "/org/bluez/app"
        self.services = []

    def add_service(self, service):
        self.services.append(service)

    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        res = {}
        for s in self.services:
            res[s.path] = {
                'org.bluez.GattService1': {
                    'UUID': Variant('s', s.uuid),
                    'Primary': Variant('b', s.primary)
                }
            }
            for c in s.characteristics:
                res[c.path] = {
                    'org.bluez.GattCharacteristic1': {
                        'UUID': Variant('s', c.uuid),
                        'Service': Variant('o', s.path),
                        'Flags': Variant('as', c.flags)
                    }
                }
        return res


class CCCDescriptor(ServiceInterface):
    """Client Characteristic Configuration Descriptor"""

    def __init__(self, characteristic_path):
        super().__init__('org.bluez.GattDescriptor1')
        self.path = f"{characteristic_path}/desc0"
        self.value = bytearray([0x00, 0x00])  # Initial: notifications disabled

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return '00002902-0000-1000-8000-00805f9b34fb'

    @dbus_property(access=PropertyAccess.READ)
    def Characteristic(self) -> 'o':
        return self.path.rsplit('/desc0', 1)[0]

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> 'as':
        return ['read', 'write']

    @method()
    def ReadValue(self, options: 'a{sv}') -> 'ay':
        return list(self.value)

    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}'):
        self.value = bytearray(value)
        # Update notifying flag on characteristic
        characteristic_path = self.path.rsplit('/desc0', 1)[0]
        # You'll need to access the characteristic to set notifying
        logger.info(f"CCCD write: {value.hex()}")


class BLEServer:
    """BLE Server using dbus-next with ObjectManager"""

    def __init__(self, command_handler):
        self.command_handler = command_handler
        self.bus = None

    async def start(self):
        try:
            self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

            # 1. Configure adapter first
            introspection = await self.bus.introspect('org.bluez', '/org/bluez/hci0')
            bluez = self.bus.get_proxy_object(
                'org.bluez', '/org/bluez/hci0', introspection)
            adapter = bluez.get_interface('org.bluez.Adapter1')
            adapter_props = bluez.get_interface(
                'org.freedesktop.DBus.Properties')

            # Set adapter properties
            await adapter_props.call_set('org.bluez.Adapter1', 'Powered', Variant('b', True))
            await adapter_props.call_set('org.bluez.Adapter1', 'Alias', Variant('s', 'UDS-CAN-Bridge'))
            await adapter_props.call_set('org.bluez.Adapter1', 'Discoverable', Variant('b', True))
            logger.info("Bluetooth adapter configured")

            # 2. Create and register Advertisement
            advertisement = LEAdvertisement()
            self.bus.export(advertisement.path, advertisement)

            le_advertising = bluez.get_interface(
                'org.bluez.LEAdvertisingManager1')
            await le_advertising.call_register_advertisement(advertisement.path, {})
            logger.info("Advertisement registered")

            # 3. Create GATT Service and Characteristic
            service = GATTService(0, SERVICE_UUID, True)
            char = GATTCharacteristic(0, CHARACTERISTIC_UUID,
                                      ['read', 'write', 'notify'],
                                      service.path, self.command_handler)
            descriptor = CCCDescriptor(char.path)
            service.add_characteristic(descriptor)

            # 4. Create Application Root with ObjectManager
            app = GATTApplication()
            app.add_service(service)

            # 5. Export all to the bus
            self.bus.export(app.path, app)
            self.bus.export(service.path, service)
            self.bus.export(char.path, char)

            # 6. Register with BlueZ GattManager1
            gatt_manager = bluez.get_interface('org.bluez.GattManager1')
            await gatt_manager.call_register_application(app.path, {})

            logger.info(
                "BLE server started successfully - GATT application registered")
            logger.info(f"Service Path: {service.path}")
            logger.info(f"Characteristic Path: {char.path}")
            logger.info("Advertising as 'UDS-CAN-Bridge'")

            # Keep running
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"BLE server error: {e}")
            raise

    async def stop(self):
        if self.bus:
            self.bus.disconnect()
            logger.info("BLE server stopped")
