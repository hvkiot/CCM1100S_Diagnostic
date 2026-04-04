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
        """Perform security access sequence"""
        logger.info("Starting security access...")

        # Step 1: Request seed
        seed_response = uds_client.raw_request(bytes([0x27, level]))
        if not seed_response or seed_response[0] != 0x67:
            logger.error("Failed to get seed")
            return False

        seed = seed_response[2:]
        logger.debug(f"Received seed: {seed.hex()}")

        # Step 2: Calculate key
        try:
            key = self.calculate_key(seed)
        except Exception as e:
            logger.error(f"Key calculation failed: {e}")
            return False

        # Step 3: Send key
        verify_response = uds_client.raw_request(
            bytes([0x27, level + 1]) + key)

        if verify_response and verify_response[0] == 0x67:
            self._is_unlocked = True
            logger.info("Security access granted!")
            return True
        else:
            logger.error("Security access denied")
            return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
