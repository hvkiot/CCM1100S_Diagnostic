"""CAN Bus Configuration"""

# CAN Interface Settings
CAN_CONFIG = {
    'channel': 'can1',
    'bitrate': 250000,
    'interface': 'socketcan'
}

# UDS Communication IDs
UDS_IDS = {
    'request': 0x1BDA08F1,
    'response': 0x1BDAF108,
    'functional': 0x18DB33F1
}

# UDS Commands
UDS_COMMANDS = {
    'read_data': 0x22,
    'write_data': 0x2E,
    'diagnostic_session': 0x10,
    'ecu_reset': 0x11,
    'positive_response': 0x62,
    'negative_response': 0x7F
}

# Timeouts (seconds)
TIMEOUTS = {
    'wakeup': 0.2,
    'query': 2.0,
    'flow_control': 0.05,
    'session_hold': 0.05
}

# J1939 Broadcast IDs
J1939_IDS = {
    'axle_gauge': 0x18FF0108,
    'error_current': 0x18FF0208,
    'solenoid_status': 0x18FF0308
}