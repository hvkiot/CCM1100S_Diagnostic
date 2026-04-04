# /ble/protocol.py
from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass, asdict


class CommandType(Enum):
    READ_DID = "read_did"
    WRITE_DID = "write_did"
    READ_VIN = "read_vin"
    WRITE_VIN = "write_vin"
    SECURITY_ACCESS = "security_access"
    DIAGNOSTIC_SESSION = "diagnostic_session"
    ROUTINE_CONTROL = "routine_control"
    GET_STATUS = "get_status"


@dataclass
class UDSCommand:
    """Command structure for Flutter communication"""
    command: CommandType
    id: int
    params: Dict[str, Any]

    def to_json(self) -> Dict:
        return {
            'command': self.command.value,
            'id': self.id,
            **self.params
        }

    @classmethod
    def from_json(cls, data: Dict):
        return cls(
            command=CommandType(data.get('command')),
            id=data.get('id', 0),
            params={k: v for k, v in data.items() if k not in [
                'command', 'id']}
        )


@dataclass
class UDSResponse:
    """Response structure for Flutter communication"""
    success: bool
    id: int
    data: Any = None
    error: str = None

    def to_json(self) -> Dict:
        result = {
            'success': self.success,
            'id': self.id
        }
        if self.data is not None:
            result['data'] = self.data
        if self.error is not None:
            result['error'] = self.error
        return result
