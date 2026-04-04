# /ble/command_handler.py
import asyncio
from typing import Dict, Any, Optional
from core.uds_client import UDSClient
from utils.logger import get_logger
from utils.validators import validate_vin, validate_did

logger = get_logger(__name__)


class CommandHandler:
    """Handle commands from Flutter app"""

    def __init__(self, uds_client: UDSClient):
        self.uds_client = uds_client
        self._pending_operations = {}

    async def _process_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for handle_command - maintains compatibility"""
        return await self.handle_command(message)

    async def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Route command to appropriate handler"""
        cmd_type = command.get('command')
        cmd_id = command.get('id', 0)

        handlers = {
            'read_did': self._handle_read_did,
            'write_did': self._handle_write_did,
            'read_vin': self._handle_read_vin,
            'write_vin': self._handle_write_vin,
            'security_access': self._handle_security_access,
            'diagnostic_session': self._handle_diagnostic_session,
            'routine_control': self._handle_routine_control,
            'get_status': self._handle_get_status,
        }

        handler = handlers.get(cmd_type)
        if handler:
            result = await handler(command)
            result['id'] = cmd_id
            return result
        else:
            return {'error': f'Unknown command: {cmd_type}', 'id': cmd_id}

    async def _handle_read_did(self, command: Dict) -> Dict:
        """Handle read DID request"""
        did_str = command.get('did', '')

        try:
            did = validate_did(did_str)
            data = await asyncio.get_event_loop().run_in_executor(
                None, self.uds_client.read_data_by_identifier, did
            )

            if data:
                return {
                    'success': True,
                    'did': f"0x{did:04X}",
                    'data': data.hex(),
                    'ascii': self._try_decode_ascii(data)
                }
            else:
                return {'success': False, 'error': 'No response from ECU'}

        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.exception("Read DID failed")
            return {'success': False, 'error': f'Communication error: {e}'}

    async def _handle_write_did(self, command: Dict) -> Dict:
        """Handle write DID request"""
        did_str = command.get('did', '')
        data_hex = command.get('data', '')

        try:
            did = validate_did(did_str)
            data = bytes.fromhex(data_hex)

            success = await asyncio.get_event_loop().run_in_executor(
                None, self.uds_client.write_data_by_identifier, did, data
            )

            return {
                'success': success,
                'did': f"0x{did:04X}",
                'message': 'Write successful' if success else 'Write failed'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _handle_read_vin(self, command: Dict) -> Dict:
        """Handle read VIN request"""
        vin = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client.read_vin
        )

        if vin:
            return {'success': True, 'vin': vin}
        else:
            return {'success': False, 'error': 'Failed to read VIN'}

    async def _handle_write_vin(self, command: Dict) -> Dict:
        """Handle write VIN request"""
        vin = command.get('vin', '')

        if not validate_vin(vin):
            return {'success': False, 'error': 'Invalid VIN format'}

        success = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client.write_vin, vin
        )

        return {
            'success': success,
            'message': 'VIN written successfully' if success else 'VIN write failed'
        }

    async def _handle_security_access(self, command: Dict) -> Dict:
        """Handle security access request"""
        level = command.get('level', 0x01)

        success = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client.security_manager.do_security_access,
            self.uds_client, level
        )

        return {
            'success': success,
            'message': 'Security access granted' if success else 'Security access denied'
        }

    async def _handle_diagnostic_session(self, command: Dict) -> Dict:
        """Handle diagnostic session control"""
        session = command.get('session', 'extended')

        from core.uds_client import UDSSessionType
        session_map = {
            'default': UDSSessionType.DEFAULT,
            'programming': UDSSessionType.PROGRAMMING,
            'extended': UDSSessionType.EXTENDED
        }

        session_type = session_map.get(
            session.lower(), UDSSessionType.EXTENDED)

        success = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client._diagnostic_session_control, session_type
        )

        return {
            'success': success,
            'session': session,
            'message': f'Switched to {session} session' if success else 'Session switch failed'
        }

    async def _handle_routine_control(self, command: Dict) -> Dict:
        """Handle routine control"""
        routine_id = command.get('routine_id', 0)
        subfunction = command.get('subfunction', 0x01)
        data_hex = command.get('data', '')

        data = bytes.fromhex(data_hex) if data_hex else b''

        response = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client.routine_control, routine_id, subfunction, data
        )

        if response:
            return {
                'success': True,
                'response': response.hex(),
                'data': response[4:].hex() if len(response) > 4 else ''
            }
        else:
            return {'success': False, 'error': 'No response from ECU'}

    async def _handle_get_status(self, command: Dict) -> Dict:
        """Get current system status"""
        return await self.get_status()

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of UDS client"""
        return {
            'connected': self.uds_client.can_manager._is_connected,
            'authenticated': self.uds_client._is_authenticated,
            'session': self.uds_client._current_session.name if self.uds_client._current_session else 'None',
            'security_unlocked': self.uds_client.security_manager.is_unlocked
        }

    def _try_decode_ascii(self, data: bytes) -> Optional[str]:
        """Try to decode data as ASCII"""
        try:
            # Skip first byte (response code for read)
            ascii_data = data[1:].decode('ascii', errors='ignore')
            if ascii_data.strip():
                return ascii_data
        except:
            pass
        return None
