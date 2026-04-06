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

    def do_security_access(self, uds_client, level: int = 0x03) -> bool:
        """Perform security access sequence - try level 0x03"""
        logger.info("Starting security access...")

        # Try multiple levels
        for test_level in [0x03, 0x05, 0x07, 0x09, 0x01]:
            logger.info(f"Trying security level 0x{test_level:02X}")

            # Step 1: Request seed
            seed_response = uds_client.raw_request(bytes([0x27, test_level]))

            if not seed_response:
                logger.warning(f"No response for level 0x{test_level:02X}")
                continue

            # Check for positive response (0x67)
            if seed_response[0] == 0x67:
                seed = seed_response[2:]
                logger.info(
                    f"✅ Got seed for level 0x{test_level:02X}: {seed.hex()}")

                # Step 2: Calculate key
                try:
                    key = self.calculate_key(seed)
                    logger.info(f"Calculated key: {key.hex()}")
                except Exception as e:
                    logger.error(f"Key calculation failed: {e}")
                    continue

                # Step 3: Send key
                verify_response = uds_client.raw_request(
                    bytes([0x27, test_level + 1]) + key)

                if verify_response and verify_response[0] == 0x67:
                    self._is_unlocked = True
                    logger.info(
                        f"✅ Security access granted at level 0x{test_level:02X}!")
                    return True
                else:
                    nrc = verify_response[2] if verify_response and len(
                        verify_response) > 2 else 0x00
                    logger.warning(
                        f"Key rejected for level 0x{test_level:02X}, NRC: 0x{nrc:02X}")
            else:
                nrc = seed_response[2] if len(seed_response) > 2 else 0x00
                logger.warning(
                    f"Seed request failed for level 0x{test_level:02X}: NRC 0x{nrc:02X}")

        logger.error("All security levels failed")
        return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
