"""
log_helper.py

Reusable logging configuration for the rag_chat project.

Provides:
    - DEFAULT_LOG_FORMAT
    - DEFAULT_DATE_FORMAT
    - DEFAULT_MAX_BYTES (10 MB)
    - DEFAULT_BACKUP_COUNT (3)
    - DEFAULT_LOG_LEVEL (INFO)
    - setup_logging(log_dir, log_name, ...) -> logging.Logger

Design notes:
    - Uses RotatingFileHandler so logs do not grow unbounded.
    - Format includes timestamp, level, logger name and message.
    - Uses lazy %-style formatting at call sites to avoid cost when
      the log level is filtered out (logging itself does the work).
    - A StreamHandler writes to stderr so console output is also
      captured by anyone launching the module.
    - setup_logging is idempotent: calling it twice with the same
      logger name will not duplicate handlers.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


# --------------------------------------------------
# Configuration constants
# --------------------------------------------------

DEFAULT_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

DEFAULT_BACKUP_COUNT = 3

DEFAULT_LOG_LEVEL = logging.INFO

DEFAULT_ENCODING = "utf-8"

_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _log_level_from_env() -> int:
    raw = os.getenv("RALG_LOG_LEVEL", "").strip().upper()
    if not raw:
        return DEFAULT_LOG_LEVEL
    return _LOG_LEVEL_MAP.get(raw, DEFAULT_LOG_LEVEL)


# --------------------------------------------------
# Reusable formatters
# --------------------------------------------------

def make_formatter(
    fmt: str = DEFAULT_LOG_FORMAT,
    datefmt: str = DEFAULT_DATE_FORMAT,
) -> logging.Formatter:
    """
    Build a Formatter instance with the standard project format.
    """
    return logging.Formatter(
        fmt=fmt,
        datefmt=datefmt,
    )


def make_console_formatter() -> logging.Formatter:
    """
    Slightly shorter format for the console handler.
    """
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt=DEFAULT_DATE_FORMAT,
    )


# --------------------------------------------------
# Setup
# --------------------------------------------------

def setup_logging(
    log_dir,
    log_name: str = "rag_chat",
    log_level: int | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    log_to_console: bool = True,
) -> logging.Logger:
    """
    Configure rotating-file logging for the rag_chat project.

    Parameters
    ----------
    log_dir : str | os.PathLike
        Directory where the log file will be created. Created if
        missing.
    log_name : str
        Base name for the log file (without extension) AND the
        name of the logger that will be returned.
    log_level : int | None
        Logging level (e.g. logging.INFO, logging.DEBUG). When None,
        reads RALG_LOG_LEVEL environment variable; falls back to
        DEFAULT_LOG_LEVEL on missing/invalid value.
    max_bytes : int
        Maximum size of a single log file before rotation.
    backup_count : int
        Number of rotated backups to retain.
    log_to_console : bool
        If True, also attach a StreamHandler so logs are echoed
        to stderr.

    Returns
    -------
    logging.Logger
        The configured logger, ready for use.

    Notes
    -----
    This function is idempotent for a given logger name. Calling
    it again will replace the existing handlers rather than
    stacking duplicates, which keeps log output from being printed
    twice if a module is imported more than once.
    """
    log_path = Path(log_dir)
    log_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_file = log_path / f"{log_name}.log"

    effective_level = log_level if log_level is not None else _log_level_from_env()

    logger = logging.getLogger(log_name)
    logger.setLevel(effective_level)

    # Remove any pre-existing handlers so we do not accumulate
    # duplicates across repeated calls or test invocations.
    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    # Propagate=False keeps root-logger config from doubling
    # output in environments where the root logger is also
    # configured (e.g. pytest, some IDEs).
    logger.propagate = False

    file_handler = RotatingFileHandler(
        filename=str(log_file),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding=DEFAULT_ENCODING,
        delay=True,  # open file lazily so startup stays fast
    )
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(make_formatter())

    logger.addHandler(file_handler)

    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(effective_level)
        console_handler.setFormatter(make_console_formatter())
        logger.addHandler(console_handler)

    return logger


def get_logger(
    name: str = "rag_chat",
) -> logging.Logger:
    """
    Return an already-configured logger by name. If setup_logging
    has not yet been called for that name, the logger will still
    be returned but will only emit at WARNING and above unless
    the root logger has been configured separately.
    """
    return logging.getLogger(name)