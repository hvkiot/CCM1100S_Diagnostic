# /core/security_manager.py
from Crypto.Cipher import AES
import time
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

        # Critical: Wait for ECU to be ready
        time.sleep(0.3)

        # Step 1: Request seed
        logger.info("Requesting seed...")
        seed_response = uds_client.raw_request(bytes([0x27, level]))

        if not seed_response:
            logger.error("No response to seed request")
            return False

        # Check if we got a multi-frame response (0x10) or positive response (0x67)
        if seed_response[0] == 0x10:
            # This is a First Frame - we need to extract the actual response
            # The ISO-TP layer should have already reassembled it
            logger.error(
                f"Got multi-frame header instead of response: {seed_response.hex()}")
            return False

        if seed_response[0] != 0x67:
            nrc = seed_response[2] if len(seed_response) > 2 else 0x00
            logger.error(
                f"Failed to get seed. Response: {seed_response.hex()}, NRC: 0x{nrc:02X}")
            return False

        seed = seed_response[2:]
        logger.info(f"Received seed ({len(seed)} bytes): {seed.hex()}")

        # Wait before sending key
        time.sleep(0.1)

        # Step 2: Calculate key
        try:
            key = self.calculate_key(seed)
            logger.info(f"Calculated key: {key.hex()}")
        except Exception as e:
            logger.error(f"Key calculation failed: {e}")
            return False

        # Step 3: Send key
        logger.info("Sending key...")
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
