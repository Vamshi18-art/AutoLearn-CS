# job_module/logger.py
# Shared logger — imported by every module in this package.

import logging
import sys
from job_module.config import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger wired to stdout.
    Call once per module:  logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if not logger.handlers:                          # avoid duplicate handlers
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    return logger