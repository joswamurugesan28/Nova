"""Logging setup for NOVA.

Configures the ``nova`` logger with:

* a rotating file handler writing to the configured log file (default ``logs/nova.log``)
* a console handler (WARNING+ by default so INFO chatter stays in the log only)

``setup_logging`` is idempotent: calling it more than once replaces
handlers instead of duplicating them.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from nova.config import LoggingSettings

LOGGER_NAME = "nova"

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the ``nova`` namespace."""
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def setup_logging(settings: LoggingSettings | None = None,
                  console_level: str = "WARNING") -> logging.Logger:
    """Configure and return the root ``nova`` logger.

    Args:
        settings: logging configuration; built-in defaults if omitted.
        console_level: minimum level shown on the console.
    """
    settings = settings or LoggingSettings()
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(settings.level)

    # Idempotency: drop any handlers installed by a previous call.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    log_path: Path = settings.path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=settings.max_bytes, backupCount=settings.backup_count
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(settings.level)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(getattr(logging, console_level.upper(), logging.WARNING))
    logger.addHandler(console)

    logger.propagate = False
    return logger
