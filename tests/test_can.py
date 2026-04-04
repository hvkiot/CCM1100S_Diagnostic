import asyncio
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, dbus_property, signal
from dbus_next.constants import PropertyAccess, BusType
from dbus_next import Variant

SERVICE_UUID = "12345678-1234-1234-1234-123456789ABC"
CHARACTERISTIC_UUID = "87654321-4321-4321-4321-CBA987654321"


class Characteristic(ServiceInterface):
    def __init__(self, uuid, flags, service_path):
        super().__init__('org.bluez.GattCharacteristic1')
        self.path = f"{service_path}/char0"
        self.uuid = uuid
        self.flags = flags
        self.service_path = service_path

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
        print(f"Received: {bytes(value)}")

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


class Application(ServiceInterface):
    def __init__(self):
        super().__init__('org.freedesktop.DBus.ObjectManager')
        self.path = "/org/bluez/app"
        self.services = []

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
        return 'UDS-CAN-Bridge'

    @method()
    def Release(self):
        print("Advertisement released")


async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    app = Application()
    service = Service(SERVICE_UUID, True)
    char = Characteristic(CHARACTERISTIC_UUID, [
                          'read', 'write', 'notify'], service.path)
    adv = Advertisement()

    service.characteristics.append(char)
    app.services.append(service)

    bus.export(app.path, app)
    bus.export(service.path, service)
    bus.export(char.path, char)
    bus.export(adv.path, adv)

    # Get BlueZ interfaces
    introspection = await bus.introspect('org.bluez', '/org/bluez/hci0')
    bluez = bus.get_proxy_object('org.bluez', '/org/bluez/hci0', introspection)

    # Register GATT application
    gatt_manager = bluez.get_interface('org.bluez.GattManager1')
    await gatt_manager.call_register_application(app.path, {})
    print("✅ GATT application registered")

    # Register advertisement
    le_ad_manager = bluez.get_interface('org.bluez.LEAdvertisingManager1')
    await le_ad_manager.call_register_advertisement(adv.path, {})
    print("✅ Advertisement registered")

    print("BLE server running. Scan with your phone.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
