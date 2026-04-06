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

        # Send Tester Present to keep session alive
        logger.info("Sending Tester Present...")
        uds_client.raw_request(bytes([0x3E, 0x00]))
        time.sleep(0.2)

        # Step 1: Request seed (may need retry)
        for attempt in range(3):
            logger.info(f"Requesting seed (attempt {attempt+1})...")
            seed_response = uds_client.raw_request(bytes([0x27, level]))

            if seed_response and seed_response[0] == 0x67:
                break

            if seed_response and seed_response[0] == 0x7F:
                nrc = seed_response[2] if len(seed_response) > 2 else 0x00
                logger.warning(f"Attempt {attempt+1} failed: NRC 0x{nrc:02X}")
                time.sleep(0.3)
                continue
            else:
                logger.warning(
                    f"Attempt {attempt+1} failed: no valid response")
                time.sleep(0.3)
        else:
            logger.error("All attempts to get seed failed")
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
