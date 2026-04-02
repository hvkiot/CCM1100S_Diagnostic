"""Solenoid Status Data Model"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass
class SolenoidStatus:
    """Solenoid status data model"""
    timestamp: datetime
    load_solenoid: str = "OFF"
    a5_lock1: str = "OFF"
    a5_lock2: str = "OFF"
    a6_lock1: str = "OFF"
    a6_lock2: str = "OFF"
    
    # Status values mapping
    STATUS_MAP = {
        0: "OFF",
        1: "ON",
        2: "ERROR",
        3: "NOT AVAILABLE"
    }
    
    @classmethod
    def from_raw(cls, raw_data: Dict[str, int]) -> 'SolenoidStatus':
        """Create SolenoidStatus from raw data"""
        return cls(
            timestamp=datetime.now(),
            load_solenoid=cls.STATUS_MAP.get(raw_data.get('Load Solenoid', 0), "UNKNOWN"),
            a5_lock1=cls.STATUS_MAP.get(raw_data.get('A5 Lock Valve 1', 0), "UNKNOWN"),
            a5_lock2=cls.STATUS_MAP.get(raw_data.get('A5 Lock Valve 2', 0), "UNKNOWN"),
            a6_lock1=cls.STATUS_MAP.get(raw_data.get('A6 Lock Valve 1', 0), "UNKNOWN"),
            a6_lock2=cls.STATUS_MAP.get(raw_data.get('A6 Lock Valve 2', 0), "UNKNOWN"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'load_solenoid': self.load_solenoid,
            'a5_lock1': self.a5_lock1,
            'a5_lock2': self.a5_lock2,
            'a6_lock1': self.a6_lock1,
            'a6_lock2': self.a6_lock2,
        }
    
    def get_status_color(self, status: str) -> str:
        """Get color code for status display"""
        colors = {
            "ON": "green",
            "OFF": "gray",
            "ERROR": "red",
            "NOT AVAILABLE": "orange",
            "UNKNOWN": "yellow"
        }
        return colors.get(status, "gray")
    
    def get_icon(self, status: str) -> str:
        """Get emoji icon for status"""
        icons = {
            "ON": "🔵",
            "OFF": "⚪",
            "ERROR": "🔴",
            "NOT AVAILABLE": "⚫",
            "UNKNOWN": "❓"
        }
        return icons.get(status, "⚪")
    
    def is_any_error(self) -> bool:
        """Check if any solenoid has error"""
        return any([
            self.load_solenoid == "ERROR",
            self.a5_lock1 == "ERROR",
            self.a5_lock2 == "ERROR",
            self.a6_lock1 == "ERROR",
            self.a6_lock2 == "ERROR",
        ])
    
    def get_error_list(self) -> list:
        """Get list of solenoids with errors"""
        errors = []
        if self.load_solenoid == "ERROR":
            errors.append("Load Solenoid")
        if self.a5_lock1 == "ERROR":
            errors.append("A5 Lock Valve 1")
        if self.a5_lock2 == "ERROR":
            errors.append("A5 Lock Valve 2")
        if self.a6_lock1 == "ERROR":
            errors.append("A6 Lock Valve 1")
        if self.a6_lock2 == "ERROR":
            errors.append("A6 Lock Valve 2")
        return errors