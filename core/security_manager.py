# /core/security_manager.py
from Crypto.Cipher import AES
from typing import Optional
from config.settings import SecurityConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class SecurityManager:
    """Security Access (0x27) service manager"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self._is_unlocked = False

    def calculate_key(self, seed: bytes) -> bytes:
        """Calculate key from seed using AES-ECB"""
        if len(seed) != 16:
            raise ValueError(f"Seed must be 16 bytes, got {len(seed)}")

        cipher = AES.new(self.config.secret_key, AES.MODE_ECB)
        key = cipher.encrypt(seed)
        logger.debug(f"Calculated key: {key.hex()}")
        return key

    def do_security_access(self, uds_client, level: int = 0x01) -> bool:
        """Perform security access sequence - handles multi-frame seed"""
        logger.info("Starting security access...")

        # Step 1: Request seed
        seed_response = uds_client.raw_request(bytes([0x27, level]))

        if not seed_response:
            logger.error("No response to seed request")
            return False

        # Check for positive response (0x67) - handles both single and multi-frame
        if seed_response[0] != 0x67:
            nrc = seed_response[2] if len(seed_response) > 2 else 0x00
            logger.error(
                f"Failed to get seed. Response: {seed_response.hex()}, NRC: 0x{nrc:02X}")
            return False

        # Extract seed - skip 0x67 and level byte
        if len(seed_response) >= 3:
            seed = seed_response[2:]
            logger.info(f"Received seed ({len(seed)} bytes): {seed.hex()}")
        else:
            logger.error(f"Invalid seed response length: {len(seed_response)}")
            return False

        # Step 2: Calculate key
        try:
            key = self.calculate_key(seed)
            logger.info(f"Calculated key: {key.hex()}")
        except Exception as e:
            logger.error(f"Key calculation failed: {e}")
            return False

        # Step 3: Send key
        verify_response = uds_client.raw_request(
            bytes([0x27, level + 1]) + key)

        if verify_response and verify_response[0] == 0x67:
            self._is_unlocked = True
            logger.info("✅ Security access granted!")
            return True
        else:
            nrc = verify_response[2] if verify_response and len(
                verify_response) > 2 else 0x00
            logger.error(f"Security access denied. NRC: 0x{nrc:02X}")
            return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
