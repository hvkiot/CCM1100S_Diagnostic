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

        from core.uds_client import UDSSessionType

        # 1. Force the session ONCE, just like check.py
        logger.info("Forcing Extended Session (0x10 0x03)...")
        if not uds_client.diagnostic_session_control(UDSSessionType.EXTENDED):
            logger.error(
                "Failed to enter Extended Session. Security will likely fail.")

        # Give the ECU time to settle after the session switch
        time.sleep(0.5)

        # Try multiple attempts with increasing delays
        for attempt in range(3):  # Reduced to 3 attempts to avoid long lockouts
            logger.info(f"Requesting seed (attempt {attempt+1})...")

            # Step 1: Request seed
            seed_response = uds_client.raw_request(bytes([0x27, level]))

            # Check if response is valid (0x67 is positive response for 0x27)
            if seed_response and seed_response[0] == 0x67:
                seed = seed_response[2:]
                logger.info(f"✅ Got valid seed: {seed.hex()}")

                # Calculate and send key
                key = self.calculate_key(seed)

                # Small delay before sending key (STmin compliance)
                time.sleep(0.05)

                verify_response = uds_client.raw_request(
                    bytes([0x27, level + 1]) + key)

                if verify_response and verify_response[0] == 0x67:
                    self._is_unlocked = True
                    logger.info("✅ Security access granted!")
                    return True
                else:
                    nrc = verify_response[2] if verify_response and len(
                        verify_response) > 2 else 0x00
                    logger.warning(f"Key rejected: NRC 0x{nrc:02X}")
                    return False  # If key is rejected, retry loop is usually locked out by ECU anyway
            else:
                nrc = seed_response[2] if seed_response and len(
                    seed_response) > 2 else 0x00
                logger.warning(f"Attempt {attempt+1} failed: NRC 0x{nrc:02X}")

            # Increase delay between attempts if seed failed
            time.sleep(1.0)

        logger.error("All security attempts failed")
        return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
