#!/usr/bin/env python3
"""
BLE Server using BlueZ D-Bus API
Implements GATT Service for UDS communication
"""

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import json
import threading
import asyncio
from utils.logger import get_logger

logger = get_logger(__name__)

# UUIDs for our service (matching your Flutter app)
SERVICE_UUID = "12345678-1234-1234-1234-123456789ABC"
CHARACTERISTIC_UUID = "87654321-4321-4321-4321-CBA987654321"


class UDSCharacteristic(dbus.service.Object):
    """GATT Characteristic for UDS commands"""

    def __init__(self, bus, index, command_handler):
        self.path = f"/org/bluez/hci0/service0/char{index}"
        self.bus = bus
        self.command_handler = command_handler
        self.notifying = False

        dbus.service.Object.__init__(self, bus, self.path)

    @dbus.service.method('org.bluez.GattCharacteristic1',
                         in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        """Handle read requests from client"""
        try:
            status = self.command_handler.get_status()
            value = json.dumps(status).encode('utf-8')
            logger.debug(f"BLE read: {status}")
            return dbus.Array(value, signature='y')
        except Exception as e:
            logger.error(f"Read error: {e}")
            return dbus.Array([], signature='y')

    @dbus.service.method('org.bluez.GattCharacteristic1',
                         in_signature='aya{sv}', out_signature='')
    def WriteValue(self, value, options):
        """Handle write requests from client"""
        try:
            data = bytes(value)
            message = json.loads(data.decode('utf-8'))
            logger.info(f"BLE command received: {message.get('command')}")

            # Process in background thread
            thread = threading.Thread(
                target=self._process_command,
                args=(message,),
                daemon=True
            )
            thread.start()

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Write error: {e}")

    @dbus.service.method('org.bluez.GattCharacteristic1',
                         in_signature='', out_signature='')
    def StartNotify(self):
        """Start notifications"""
        self.notifying = True
        logger.info("BLE notifications started")

    @dbus.service.method('org.bluez.GattCharacteristic1',
                         in_signature='', out_signature='')
    def StopNotify(self):
        """Stop notifications"""
        self.notifying = False
        logger.info("BLE notifications stopped")

    def _process_command(self, message):
        """Process command and send notification"""
        try:
            # Create new event loop for async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self.command_handler.handle_command(message)
            )
            loop.close()

            # Send notification if enabled
            if self.notifying:
                response_bytes = json.dumps(response).encode('utf-8')
                self.PropertiesChanged(
                    'org.bluez.GattCharacteristic1',
                    {'Value': dbus.Array(response_bytes, signature='y')},
                    []
                )
                logger.debug(f"Notification sent: {response}")

        except Exception as e:
            logger.error(f"Command processing error: {e}")

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        """Get property value"""
        if interface == 'org.bluez.GattCharacteristic1':
            if prop == 'UUID':
                return CHARACTERISTIC_UUID
            elif prop == 'Flags':
                return dbus.Array(['read', 'write', 'notify'], signature='s')
            elif prop == 'Value':
                return dbus.Array([], signature='y')
        raise dbus.exceptions.DBusException(
            'org.freedesktop.DBus.Error.InvalidArgs',
            f"Property {prop} not found"
        )

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='sa{sv}as', out_signature='')
    def PropertiesChanged(self, interface, changed, invalidated):
        """Signal property changes"""
        pass


class UDSService(dbus.service.Object):
    """GATT Service for UDS"""

    def __init__(self, bus, command_handler):
        self.path = '/org/bluez/hci0/service0'
        self.bus = bus
        self.command_handler = command_handler

        dbus.service.Object.__init__(self, bus, self.path)

        # Create characteristic
        self.characteristic = UDSCharacteristic(bus, 0, command_handler)

    @dbus.service.method('org.freedesktop.DBus.Properties',
                         in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        """Get property value"""
        if interface == 'org.bluez.GattService1':
            if prop == 'UUID':
                return SERVICE_UUID
            elif prop == 'Primary':
                return True
            elif prop == 'Characteristics':
                return dbus.Array([self.characteristic.path], signature='o')
        raise dbus.exceptions.DBusException(
            'org.freedesktop.DBus.Error.InvalidArgs',
            f"Property {prop} not found"
        )


class BLEServer:
    """BLE Server Manager"""

    def __init__(self, command_handler):
        self.command_handler = command_handler
        self.mainloop = None
        self.service = None
        self.application_path = '/org/bluez/hci0/service0'

    def start(self):
        """Start BLE server"""
        try:
            # Initialize D-Bus main loop
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

            # Get system bus
            bus = dbus.SystemBus()

            # Get BlueZ adapter
            adapter_obj = bus.get_object('org.bluez', '/org/bluez/hci0')
            adapter = dbus.Interface(adapter_obj, 'org.bluez.Adapter1')

            # Power on adapter
            # Access the standard D-Bus Properties interface
            adapter_props = dbus.Interface(
                adapter_obj, 'org.freedesktop.DBus.Properties')

            # Set properties using the correct modern interface
            adapter_props.Set('org.bluez.Adapter1',
                              'Powered', dbus.Boolean(True))
            adapter_props.Set('org.bluez.Adapter1', 'Alias',
                              dbus.String('UDS-CAN-Bridge'))
            adapter_props.Set('org.bluez.Adapter1',
                              'Discoverable', dbus.Boolean(True))

            logger.info("Bluetooth adapter configured")

            # Create GATT service
            self.service = UDSService(bus, self.command_handler)

            # Get GATT manager
            gatt_manager = dbus.Interface(
                bus.get_object('org.bluez', '/org/bluez/hci0'),
                'org.bluez.GattManager1'
            )

            # Register application
            gatt_manager.RegisterApplication(
                self.application_path,
                {},
                reply_handler=self._reg_success,
                error_handler=self._reg_error
            )

            logger.info(f"BLE Server started - Service: {SERVICE_UUID}")
            logger.info(f"Characteristic: {CHARACTERISTIC_UUID}")

            # Start GLib main loop
            self.mainloop = GLib.MainLoop()
            self.mainloop.run()

        except Exception as e:
            logger.error(f"BLE server error: {e}")
            raise

    def _reg_success(self):
        """Registration success callback"""
        logger.info("GATT application registered successfully")

    def _reg_error(self, error):
        """Registration error callback"""
        logger.error(f"Failed to register GATT application: {error}")

    def stop(self):
        """Stop BLE server"""
        if self.mainloop:
            self.mainloop.quit()
        logger.info("BLE server stopped")
