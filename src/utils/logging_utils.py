"""
logging_utils.py — Unified logger initialisation for all project scripts.

Usage:
    from src.utils.logging_utils import get_logger
    logger = get_logger(__name__)
    logger.info("message")
"""

import logging
import sys
from pathlib import Path


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Return a logger with a consistent format.

    Parameters
    ----------
    name : str
        Logger name (typically ``__name__``).
    level : int
        Logging level (default ``logging.INFO``).
    log_file : str or Path, optional
        If provided, also write logs to this file.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when called multiple times.
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — always present.
    # Force UTF-8 to avoid encoding errors on Windows with non-ASCII paths.
    console = logging.StreamHandler(
        open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    )
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler — optional.
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
