# /utils/validators.py
import re


def validate_did(did_str: str) -> int:
    """Validate and parse DID string"""
    # Remove 0x prefix and spaces
    did_str = did_str.strip().lower().replace(' ', '')

    if did_str.startswith('0x'):
        did_str = did_str[2:]

    if not re.fullmatch(r'[0-9a-f]{1,4}', did_str):
        raise ValueError(f"Invalid DID format: {did_str}")

    did = int(did_str, 16)

    if did < 0 or did > 0xFFFF:
        raise ValueError(f"DID out of range: {did}")

    return did


def validate_hex_data(data_str: str) -> bool:
    """Validate hex data string"""
    try:
        bytes.fromhex(data_str)
        return True
    except ValueError:
        return False
