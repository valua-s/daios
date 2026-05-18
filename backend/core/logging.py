from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.getenv("DAIOS_LOG_DIR", "/app/logs"))

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(service_name: str, level: int = logging.INFO) -> None:
    """Configure root logger: stdout + rotating all-levels file + rotating error-only file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)

    file_err = RotatingFileHandler(
        LOG_DIR / f"{service_name}.error.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_err.setLevel(logging.WARNING)
    file_err.setFormatter(formatter)

    root.handlers[:] = [stream, file_err]
