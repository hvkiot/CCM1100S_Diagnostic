"""DTC (Diagnostic Trouble Code) Models"""

from dataclasses import dataclass
from datetime import datetime
from typing import List
from config.did_config import DTC_CODES


@dataclass
class DTC:
    """Diagnostic Trouble Code model"""
    code: int
    description: str
    timestamp: datetime
    
    @classmethod
    def from_code(cls, code: int):
        """Create DTC from code"""
        description = DTC_CODES.get(code, f"Unknown DTC")
        return cls(code=code, description=description, timestamp=datetime.now())
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'code': f"0x{self.code:06X}",
            'description': self.description,
            'timestamp': self.timestamp.isoformat()
        }


class DTCHistory:
    """DTC History Manager"""
    
    def __init__(self):
        self.active_dtcs: List[DTC] = []
        self.history: List[DTC] = []
    
    def add_dtc(self, code: int):
        """Add DTC to active list"""
        dtc = DTC.from_code(code)
        if not self.has_dtc(code):
            self.active_dtcs.append(dtc)
            self.history.append(dtc)
    
    def clear_dtc(self, code: int):
        """Clear specific DTC"""
        self.active_dtcs = [d for d in self.active_dtcs if d.code != code]
    
    def clear_all(self):
        """Clear all active DTCs"""
        self.active_dtcs.clear()
    
    def has_dtc(self, code: int) -> bool:
        """Check if DTC is active"""
        return any(d.code == code for d in self.active_dtcs)
    
    def get_active(self) -> List[DTC]:
        """Get active DTCs"""
        return self.active_dtcs.copy()
    
    def get_history(self) -> List[DTC]:
        """Get DTC history"""
        return self.history.copy()