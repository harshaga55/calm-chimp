from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_LEVEL = os.getenv("CALM_CHIMP_LOG_LEVEL", "INFO").upper()
LOG_DIR = Path(os.getenv("CALM_CHIMP_LOG_DIR", Path.cwd() / "logs"))


def configure_logging(*, level: Optional[str] = None) -> None:
    """Configure application-wide logging with rotation-friendly file output."""

    resolved_level = getattr(logging, (level or LOG_LEVEL), logging.INFO)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    log_path = LOG_DIR / f"calmchimp-{timestamp}.log"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]

    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=handlers,
    )
