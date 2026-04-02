"""Helper Utilities for CCM1100S Diagnostic Tool"""

import struct
import time
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
import re


def bytes_to_int(data: bytes, byte_order: str = 'big') -> int:
    """Convert bytes to integer"""
    return int.from_bytes(data, byte_order)


def int_to_bytes(value: int, length: int, byte_order: str = 'big') -> bytes:
    """Convert integer to bytes"""
    return value.to_bytes(length, byte_order)


def extract_bits(data: bytes, start_bit: int, num_bits: int) -> int:
    """
    Extract bits from byte data
    start_bit: 0-based from LSB of first byte
    """
    byte_start = start_bit // 8
    bit_offset = start_bit % 8
    result = 0

    for i in range(num_bits):
        byte_idx = byte_start + (bit_offset + i) // 8
        if byte_idx >= len(data):
            break

        bit_pos = 7 - ((bit_offset + i) % 8)
        if (data[byte_idx] >> bit_pos) & 1:
            result |= (1 << (num_bits - 1 - i))

    return result


def format_hex(data: bytes, separator: str = ' ') -> str:
    """Format bytes as hex string"""
    return separator.join(f"{b:02X}" for b in data)


def parse_version(version_bytes: bytes) -> str:
    """Parse version bytes to string"""
    if len(version_bytes) >= 4:
        return f"{version_bytes[0]}.{version_bytes[1]}.{version_bytes[2]}.{version_bytes[3]}"
    return "Unknown"


def parse_ascii_string(data: bytes) -> str:
    """Parse ASCII string, stripping null bytes"""
    return data.decode('ascii', errors='ignore').strip('\x00')


def validate_can_id(can_id: int) -> bool:
    """Validate CAN ID format"""
    return 0x000 <= can_id <= 0x1FFFFFFF


def calculate_checksum(data: bytes) -> int:
    """Calculate simple XOR checksum"""
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum


class RateLimiter:
    """Rate limiter for CAN messages"""

    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    def can_call(self) -> bool:
        """Check if we can make a call"""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.period]

        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False


class DataBuffer:
    """Circular buffer for sensor data"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer = []
        self.index = 0

    def add(self, data: Any):
        """Add data to buffer"""
        if len(self.buffer) < self.max_size:
            self.buffer.append(data)
        else:
            self.buffer[self.index] = data
            self.index = (self.index + 1) % self.max_size

    def get_all(self) -> List[Any]:
        """Get all data from buffer"""
        if len(self.buffer) < self.max_size:
            return self.buffer.copy()
        return self.buffer[self.index:] + self.buffer[:self.index]

    def get_latest(self, count: int = 1) -> List[Any]:
        """Get latest N items"""
        all_data = self.get_all()
        return all_data[-count:] if all_data else []

    def clear(self):
        """Clear buffer"""
        self.buffer = []
        self.index = 0

    def size(self) -> int:
        """Get buffer size"""
        return len(self.buffer)


class Timestamp:
    """Timestamp helper"""

    @staticmethod
    def now() -> str:
        """Get current timestamp as string"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    @staticmethod
    def iso() -> str:
        """Get ISO timestamp"""
        return datetime.now().isoformat()

    @staticmethod
    def filename() -> str:
        """Get timestamp for filename"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")


class CANDataParser:
    """Helper class for parsing CAN data"""

    @staticmethod
    def parse_angle(data: bytes, start_bit: int, resolution: float = 0.1, offset: float = 0) -> float:
        """Parse angle from CAN data"""
        raw = extract_bits(data, start_bit, 16)
        if raw >= 32768:
            raw -= 65536
        return raw * resolution + offset

    @staticmethod
    def parse_current(data: bytes, start_bit: int, offset: int = 32000) -> int:
        """Parse current from CAN data"""
        raw = extract_bits(data, start_bit, 16)
        return raw - offset

    @staticmethod
    def parse_solenoid(data: bytes, start_bit: int) -> int:
        """Parse solenoid status (2 bits)"""
        return extract_bits(data, start_bit, 2)

    @staticmethod
    def parse_j1939_message(arbitration_id: int, data: bytes, mapping: Dict) -> Dict[str, Any]:
        """Parse J1939 message based on mapping"""
        result = {}

        if arbitration_id in mapping:
            for item in mapping[arbitration_id]['data']:
                start = item['start']
                bits = item['bits']
                raw = extract_bits(data, start, bits)

                if 'resolution' in item:
                    value = raw * item['resolution']
                    if 'offset' in item:
                        value += item['offset']
                    value = round(value, 2)
                else:
                    value = raw

                result[item['name']] = value

        return result


class ConnectionChecker:
    """Check connection status"""

    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
        self.last_success = time.time()
        self.consecutive_failures = 0

    def record_success(self):
        """Record successful connection"""
        self.last_success = time.time()
        self.consecutive_failures = 0

    def record_failure(self):
        """Record failed connection"""
        self.consecutive_failures += 1

    def is_connected(self) -> bool:
        """Check if connection is still active"""
        return (time.time() - self.last_success) < self.timeout

    def get_status(self) -> Tuple[bool, str]:
        """Get connection status with message"""
        if self.is_connected():
            return True, "Connected"
        elif self.consecutive_failures > 3:
            return False, "Disconnected (multiple failures)"
        else:
            return False, "No data"


class DataValidator:
    """Validate sensor data"""

    @staticmethod
    def validate_angle(angle: float) -> bool:
        """Validate angle is within range"""
        return -180 <= angle <= 180

    @staticmethod
    def validate_current(current: int) -> bool:
        """Validate current is within range"""
        return -32000 <= current <= 32000

    @staticmethod
    def validate_voltage(voltage: float) -> bool:
        """Validate voltage is within range"""
        return 9 <= voltage <= 36

    @staticmethod
    def clamp_value(value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max"""
        return max(min_val, min(value, max_val))


def retry_on_failure(max_retries: int = 3, delay: float = 0.5):
    """Decorator for retry on failure"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


def timing_decorator(func):
    """Decorator to measure execution time"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__} took {elapsed:.3f}s")
        return result
    return wrapper
