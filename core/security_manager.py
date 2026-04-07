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
        if len(seed) != 16:
            raise ValueError(f"Seed must be 16 bytes, got {len(seed)}")
        cipher = AES.new(self.config.secret_key, AES.MODE_ECB)
        return cipher.encrypt(seed)

    def do_security_access(self, uds_client, level: int = 0x01) -> bool:
        logger.info("Starting security access...")
        from core.uds_client import UDSSessionType

        logger.info("Forcing Extended Session (0x10 0x03)...")
        if not uds_client.diagnostic_session_control(UDSSessionType.EXTENDED):
            logger.error("Failed to enter Extended Session.")

        for attempt in range(3):
            logger.info(f"Requesting seed (attempt {attempt+1})...")
            seed_response = uds_client.raw_request(bytes([0x27, level]))

            if seed_response and seed_response[0] == 0x67:
                seed = seed_response[2:]

                # ----------------------------------------------------
                # THE REAL TRUTH: All-Zeros means ALREADY UNLOCKED!
                # ----------------------------------------------------
                if all(b == 0 for b in seed):
                    self._is_unlocked = True
                    logger.info(
                        "✅ ECU is ALREADY unlocked (Seed is all zeros)")
                    time.sleep(0.3)
                    return True

                logger.info(f"✅ Got valid REAL seed: {seed.hex()}")

                # Calculate key and send IMMEDIATELY (Maximum Speed!)
                key = self.calculate_key(seed)
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
                    return False
            else:
                nrc = seed_response[2] if seed_response and len(
                    seed_response) > 2 else 0x00
                logger.warning(f"Attempt {attempt+1} failed: NRC 0x{nrc:02X}")

            # Only delay if we failed and need to retry
            time.sleep(1.0)

        return False

    @property
    def is_unlocked(self) -> bool:
        return self._is_unlocked
