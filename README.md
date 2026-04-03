# CCM1100S Diagnostic Tool

A comprehensive diagnostic tool for the CCM1100S ECU, supporting UDS communication over CAN bus.

## Features

- **UDS Communication**: Full support for UDS services including ReadDataByIdentifier, WriteDataByIdentifier, and SecurityAccess.
- **ISO-TP Implementation**: Manual implementation of ISO-TP protocol for reliable multi-frame message handling.
- **Security Access**: Automatic seed-key generation and authentication for secure ECU access.
- **Interactive Console**: User-friendly command-line interface for easy navigation and testing.
- **CAN Interface**: Support for SocketCAN interface with configurable bitrate and channel.

## Installation

1.  **Clone the repository** (or download the source code).

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Running the Tool

Execute the main script to start the interactive console:

```bash
python check.py
```

### Interactive Commands

Once the tool starts, you will see a `DID>` prompt. You can enter Diagnostic Data Identifiers (DIDs) in various formats:

-   `f191`
-   `0xf191`
-   `F1 91`
-   `220F`

To exit the tool, type `exit`, `quit`, or `q`.

### Example Session

```
=== UDS DID Console (manual ISO-TP) ===
Type DID (e.g., F191, 220F) or 'exit'\n

DID> F191

--- Reading DID 0x F191 ---
[TX] 0x1bda08f1 0322f19100000000
[RX] 0x1bdaf108 6210000000000000
Final: 6210000000000000

ASCII: 

DID> exit
Exiting...
CAN shutdown done.
```

## Development

### Project Structure

The project follows a modular architecture:

```
CCM1100S_Diagnostic/
├── core/                 # Core UDS and CAN logic
│   ├── can_interface.py  # CAN bus handling
│   ├── uds_client.py     # UDS service implementations
│   ├── decoder.py        # Data decoding utilities
│   └── j1939_parser.py   # J1939 protocol support
├── config/               # Configuration files
│   ├── can_config.py     # CAN bus settings
│   └── did_config.py     # DID definitions and mappings
├── models/               # Data models
│   ├── dtc_codes.py      # DTC code definitions
│   ├── sensor_data.py    # Sensor data structures
│   └── solenoid_status.py # Solenoid status models
├── ui/                   # User interface components
│   ├── streamlit_app.py  # Main Streamlit application
│   ├── dashboard.py      # Dashboard components
│   └── components.py     # Reusable UI components
├── tests/                # Unit tests
│   ├── test_can.py       # CAN interface tests
│   └── test_decoder.py   # Decoder tests
├── utils/                # Utility functions
│   ├── logger.py         # Logging utilities
│   └── helpers.py        # General helpers
├── main.py               # Application entry point
├── check.py              # Interactive console
├── requirements.txt      # Project dependencies
└── README.md             # Project documentation
```

### Running Tests

To run the test suite, use the following command:

```bash
python -m unittest discover tests
```

## License

This project is licensed under the terms of the MIT license.
