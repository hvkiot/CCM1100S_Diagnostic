"""DID (Data Identifier) Configuration"""

# UDS Readable DIDs
UDS_DIDS = {
    0x220F: {"name": "System Voltage", "resolution": 0.1, "offset": 0, "unit": "V"},
    0x2210: {"name": "Axle 1 Angle", "resolution": 0.1, "offset": 0, "unit": "°"},
    0x2211: {"name": "Axle 5 Angle", "resolution": 0.1, "offset": 0, "unit": "°"},
    0x2212: {"name": "Axle 6 Angle", "resolution": 0.1, "offset": 0, "unit": "°"},
    0x2213: {"name": "Axle 5 Control", "resolution": 1, "offset": 0, "unit": "%"},
    0x2214: {"name": "Axle 6 Control", "resolution": 1, "offset": 0, "unit": "%"},
    0x2215: {"name": "A5 Min Current Dir1", "resolution": 1, "offset": 0, "unit": "mA"},
    0x2216: {"name": "A5 Max Current Dir1", "resolution": 1, "offset": 0, "unit": "mA"},
    0x2217: {"name": "A5 Min Current Dir2", "resolution": 1, "offset": 0, "unit": "mA"},
    0x2218: {"name": "A5 Max Current Dir2", "resolution": 1, "offset": 0, "unit": "mA"},
    0x2219: {"name": "A6 Min Current Dir1", "resolution": 1, "offset": 0, "unit": "mA"},
    0x221A: {"name": "A6 Max Current Dir1", "resolution": 1, "offset": 0, "unit": "mA"},
    0x221B: {"name": "A6 Min Current Dir2", "resolution": 1, "offset": 0, "unit": "mA"},
    0x221C: {"name": "A6 Max Current Dir2", "resolution": 1, "offset": 0, "unit": "mA"},
    0x220D: {"name": "Firmware Version", "type": "version", "multiframe": True},
    0x220E: {"name": "SW Version", "type": "version", "multiframe": False},
    0xF18C: {"name": "ECU Serial Number", "type": "uint32", "multiframe": False},
    0xF192: {"name": "ECU Product Code", "type": "uint32", "multiframe": False},
    0xF191: {"name": "ECU HW Number", "type": "ascii", "multiframe": True, "length": 15},
    0xF187: {"name": "ECU PN Number", "type": "ascii", "multiframe": True, "length": 15},
    0xF188: {"name": "ECU SW Number", "type": "ascii", "multiframe": True, "length": 15},
    0xF190: {"name": "VIN Number", "type": "ascii", "multiframe": True, "length": 17},
    0xF1A0: {"name": "VCN Number", "type": "ascii", "multiframe": True, "length": 15},
    0xF1A1: {"name": "PPN Number", "type": "ascii", "multiframe": True, "length": 17},
    0xF1A6: {"name": "VCID Number", "type": "ascii", "multiframe": True, "length": 20},
}

# J1939 Data Mapping (bit positions)
J1939_MAPPING = {
    0x18FF0108: {
        "data": [
            {"name": "Axle1 Angle", "start": 0, "bits": 16, "resolution": 1/256, "offset": -125, "unit": "°"},
            {"name": "Axle5 Angle", "start": 16, "bits": 16, "resolution": 1/256, "offset": -125, "unit": "°"},
            {"name": "Axle6 Angle", "start": 32, "bits": 16, "resolution": 1/256, "offset": -125, "unit": "°"},
        ]
    },
    0x18FF0208: {
        "data": [
            {"name": "A5 Error Angle", "start": 0, "bits": 16, "resolution": 1/256, "offset": -125, "unit": "°"},
            {"name": "A6 Error Angle", "start": 16, "bits": 16, "resolution": 1/256, "offset": -125, "unit": "°"},
            {"name": "A5 Control Current", "start": 32, "bits": 16, "resolution": 1, "offset": -32000, "unit": "mA"},
            {"name": "A6 Control Current", "start": 48, "bits": 16, "resolution": 1, "offset": -32000, "unit": "mA"},
        ]
    },
    0x18FF0308: {
        "data": [
            {"name": "Load Solenoid", "start": 0, "bits": 2},
            {"name": "A5 Lock Valve 1", "start": 2, "bits": 2},
            {"name": "A5 Lock Valve 2", "start": 4, "bits": 2},
            {"name": "A6 Lock Valve 1", "start": 6, "bits": 2},
            {"name": "A6 Lock Valve 2", "start": 8, "bits": 2},
        ],
        "solenoid_states": {
            0: "OFF",
            1: "ON",
            2: "ERROR",
            3: "NOT AVAILABLE"
        }
    }
}

# DTC Error Codes
DTC_CODES = {
    0x5A0A00: "AXLE 5 Not Turning",
    0x5A0B00: "AXLE 6 Not turning",
    0x5A0000: "AXLE 1 Sensor reading missing",
    0x5A0100: "AXLE 5 Sensor reading missing",
    0x5A0200: "AXLE 6 Sensor reading missing",
    0x5A0300: "AXLE 5 Proportional Valve Error",
    0x5A0400: "AXLE 6 Proportional Valve Error",
    0x5A0500: "AXLE 5 Lock Valve 1 Error",
    0x5A0600: "AXLE 5 Lock Valve 2 Error",
    0x5A0700: "AXLE 6 Lock Valve 1 Error",
    0x5A0800: "AXLE 6 Lock Valve 2 Error",
    0x5A0900: "LS Valve Error",
    0xC02888: "CAN Bus fault",
    0x056200: "Battery Voltage Low",
    0x056300: "Battery Voltage High",
    0x5A102F: "Vehicle Wheel Speed Signal Loss/Erratic",
    0x5A1100: "All three Angle/Encoder Sensors failed",
}