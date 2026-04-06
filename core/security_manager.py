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

        # Send Tester Present multiple times to establish session
        for _ in range(3):
            uds_client.raw_request(bytes([0x3E, 0x00]))
            time.sleep(0.1)

        # Wait longer for ECU to be ready
        time.sleep(0.5)

        # Try multiple attempts with increasing delays
        for attempt in range(5):
            logger.info(f"Requesting seed (attempt {attempt+1})...")
            seed_response = uds_client.raw_request(bytes([0x27, level]))

            if seed_response and len(seed_response) > 2:
                # Check if we got a valid seed (non-zero)
                seed = seed_response[2:]
                if seed_response[0] == 0x67 and any(b != 0 for b in seed):
                    logger.info(f"✅ Got valid seed: {seed.hex()}")

                    # Calculate and send key
                    key = self.calculate_key(seed)
                    verify_response = uds_client.raw_request(
                        bytes([0x27, level + 1]) + key)

                    if verify_response and verify_response[0] == 0x67:
                        self._is_unlocked = True
                        logger.info("✅ Security access granted!")
                        return True
                    else:
                        nrc = verify_response[2] if len(
                            verify_response) > 2 else 0x00
                        logger.warning(f"Key rejected: NRC 0x{nrc:02X}")
                else:
                    nrc = seed_response[2] if len(seed_response) > 2 else 0x00
                    logger.warning(
                        f"Attempt {attempt+1} failed: NRC 0x{nrc:02X}, seed: {seed.hex()}")

            # Increase delay between attempts
            time.sleep(0.5 * (attempt + 1))

        logger.error("All security attempts failed")
        return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
