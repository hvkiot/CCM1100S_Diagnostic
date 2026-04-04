import logging
import sys


def setup_logger(level="INFO"):
    """Configure simple readable logging"""

    # Remove any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S',
        stream=sys.stdout
    )

    # Set specific log levels
    logging.getLogger('core.can_bus').setLevel(logging.INFO)
    logging.getLogger('core.uds_client').setLevel(logging.INFO)
    logging.getLogger('ble').setLevel(logging.INFO)
    logging.getLogger('__main__').setLevel(logging.INFO)


def get_logger(name):
    """Get simple logger"""
    return logging.getLogger(name)
