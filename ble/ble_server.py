import asyncio
import json
from bleak import BleakServer, BleakGATTCharacteristic
from bleak.uuids import register_uuid
from typing import Dict, Any, Callable
from utils.logger import get_logger
from config.settings import BLEConfig

logger = get_logger(__name__)

class UDSBLEServer:
    """BLE server for Flutter app communication"""
    
    def __init__(self, config: BLEConfig, command_handler):
        self.config = config
        self.command_handler = command_handler
        self.server = None
        self.characteristic = None
        self._clients = []
        
        # Register UUIDs
        register_uuid(self.config.service_uuid, "UDS Service")
        register_uuid(self.config.characteristic_uuid, "UDS Command")
    
    async def start(self):
        """Start BLE server"""
        try:
            self.server = BleakServer(
                name=self.config.device_name,
                service_uuids=[self.config.service_uuid]
            )
            
            # Add characteristic
            self.characteristic = BleakGATTCharacteristic(
                self.config.characteristic_uuid,
                properties=["read", "write", "notify"],
                write_callback=self._on_write,
                read_callback=self._on_read
            )
            
            await self.server.start()
            logger.info(f"BLE server started as {self.config.device_name}")
            
            # Keep server running
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"Failed to start BLE server: {e}")
    
    async def _on_write(self, characteristic, data: bytearray):
        """Handle incoming BLE writes"""
        try:
            message = json.loads(data.decode('utf-8'))
            logger.info(f"Received command: {message.get('command')}")
            
            # Process command
            response = await self.command_handler.handle_command(message)
            
            # Send response back
            if response:
                await self._send_response(response)
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self._send_response({"error": "Invalid JSON format"})
        except Exception as e:
            logger.error(f"Command handling error: {e}")
            await self._send_response({"error": str(e)})
    
    async def _on_read(self, characteristic):
        """Handle BLE read requests"""
        status = await self.command_handler.get_status()
        return json.dumps(status).encode('utf-8')
    
    async def _send_response(self, response: Dict[str, Any]):
        """Send response via BLE notification"""
        if self.characteristic:
            data = json.dumps(response).encode('utf-8')
            await self.characteristic.notify(data)
            logger.debug(f"Sent response: {response}")