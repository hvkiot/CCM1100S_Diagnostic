"""Data Models for Sensor Information"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SensorData:
    """Sensor data model"""
    timestamp: datetime
    axle1_angle: Optional[float] = None
    axle5_angle: Optional[float] = None
    axle6_angle: Optional[float] = None
    a5_error: Optional[float] = None
    a6_error: Optional[float] = None
    a5_current: Optional[float] = None
    a6_current: Optional[float] = None
    system_voltage: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'axle1_angle': self.axle1_angle,
            'axle5_angle': self.axle5_angle,
            'axle6_angle': self.axle6_angle,
            'a5_error': self.a5_error,
            'a6_error': self.a6_error,
            'a5_current': self.a5_current,
            'a6_current': self.a6_current,
            'system_voltage': self.system_voltage,
        }


@dataclass
class SolenoidStatus:
    """Solenoid status model"""
    timestamp: datetime
    load_solenoid: str = "OFF"
    a5_lock1: str = "OFF"
    a5_lock2: str = "OFF"
    a6_lock1: str = "OFF"
    a6_lock2: str = "OFF"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'load_solenoid': self.load_solenoid,
            'a5_lock1': self.a5_lock1,
            'a5_lock2': self.a5_lock2,
            'a6_lock1': self.a6_lock1,
            'a6_lock2': self.a6_lock2,
        }


@dataclass
class ECUInfo:
    """ECU Information model"""
    firmware_version: str = "Unknown"
    sw_version: str = "Unknown"
    serial_number: str = "Unknown"
    product_code: str = "Unknown"
    hw_number: str = "Unknown"
    pn_number: str = "Unknown"
    vin: str = "Unknown"
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'firmware_version': self.firmware_version,
            'sw_version': self.sw_version,
            'serial_number': self.serial_number,
            'product_code': self.product_code,
            'hw_number': self.hw_number,
            'pn_number': self.pn_number,
            'vin': self.vin,
        }