from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .core import DATA_DIR, ensure_data_dir


_INITIALIZED = False


def configure_logging(level: str = "INFO", *, log_path: Optional[Path] = None) -> None:
    """Configure application-wide logging with both file and console handlers."""

    global _INITIALIZED
    if _INITIALIZED:
        return

    ensure_data_dir()
    log_file = log_path or DATA_DIR / "calm_chimp.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(str(log_file), maxBytes=1_000_000, backupCount=5)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _INITIALIZED = True
    logging.getLogger(__name__).debug("Logging configured. Output file: %s", log_file)


__all__ = ["configure_logging"]
