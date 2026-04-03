from dataclasses import dataclass
from typing import Optional

@dataclass
class CANConfig:
    interface: str = 'socketcan'
    channel: str = 'can1'
    bitrate: int = 250000
    tx_id: int = 0x1BDA08F1
    rx_id: int = 0x1BDAF108

@dataclass
class BLEConfig:
    service_uuid: str = "12345678-1234-1234-1234-123456789ABC"
    characteristic_uuid: str = "87654321-4321-4321-4321-CBA987654321"
    device_name: str = "UDS-CAN-Bridge"
    max_packet_size: int = 512

@dataclass
class SecurityConfig:
    secret_key: bytes = b"TCHRMVHA2BPX3ULC"
    security_access_level: int = 0x01