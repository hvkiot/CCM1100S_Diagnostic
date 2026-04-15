# /ble/command_handler.py
import asyncio
from typing import Dict, Any, Optional
from core.uds_client import UDSClient
from utils.logger import get_logger
from utils.validators import validate_did

logger = get_logger(__name__)


class CommandHandler:
    """Handle commands from Flutter app"""

    def __init__(self, uds_client: UDSClient):
        self.uds_client = uds_client
        self._pending_operations = {}
        self._bus_lock = asyncio.Lock()  # 🛡️ Mutex for UDS Bus

    async def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Route command with bus locking to prevent cross-talk"""
        async with self._bus_lock:
            cmd_type = command.get('command')
            cmd_id = command.get('id', 0)

            handlers = {
                'read_did': self._handle_read_did,
                'write_did': self._handle_write_did,
                'security_access': self._handle_security_access,
                'diagnostic_session': self._handle_diagnostic_session,
                'routine_control': self._handle_routine_control,
                'get_status': self._handle_get_status,
            }

            handler = handlers.get(cmd_type)
            if handler:
                result = await handler(command)
                if result.get('raw') == "43414e5f48415244574152455f4552524f52":
                    return {
                        'status': 'CAN_ERROR',
                        'success': False,
                        'message': 'Physical ECU connection lost',
                        'id': cmd_id
                    }

                result['id'] = cmd_id
                return result
            else:
                return {'error': f'Unknown command: {cmd_type}', 'id': cmd_id}

    async def _handle_read_did(self, command: Dict) -> Dict:
        did_str = command.get('did', '')

        try:
            did = validate_did(did_str)
            scaled_data = await asyncio.get_event_loop().run_in_executor(
                None, self.uds_client.read_data_by_identifier, did
            )

            if scaled_data:
                # Try to decode as ASCII for display
                try:
                    ascii_value = scaled_data.decode('ascii', errors='ignore')
                except:
                    ascii_value = scaled_data.hex()

                return {
                    'success': True,
                    'did': f"0x{did:04X}",
                    'data': scaled_data.hex() if not isinstance(scaled_data, bytes) else scaled_data.hex(),
                    'value': ascii_value,  # Human readable value
                    'raw': scaled_data.hex(),
                    'id': command.get('id')
                }
            else:
                return {'success': False, 'error': 'No response from ECU', 'id': command.get('id')}

        except Exception as e:
            return {'success': False, 'error': str(e), 'id': command.get('id')}

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
        """Get current system status via standardized response"""
        status = await self.get_status()
        is_connected = status.get('connected', False)
        
        return {
            "type": "connection_status",
            "status": "ECU_CONNECTED" if is_connected else "ECU_DISCONNECTED",
            "success": is_connected,
            "message": "ECU is online and responding" if is_connected else "ECU is offline or not responding",
            "id": command.get('id', 0)
        }

    async def get_ecu_connection_status(self) -> bool:
        """Lock-protected check for background monitor use"""
        async with self._bus_lock:
            return await asyncio.get_event_loop().run_in_executor(
                None, self.uds_client.tester_present
            )

    async def get_status(self) -> Dict[str, Any]:
        """Get current status of UDS client including real ECU check"""
        # This is called via handle_command, so it is already locked
        is_ecu_alive = await asyncio.get_event_loop().run_in_executor(
            None, self.uds_client.tester_present
        )
        
        return {
            'connected': is_ecu_alive,
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
