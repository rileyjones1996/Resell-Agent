"""Configures a rotating file + console logger for the whole application."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str,
    log_dir: Path,
    level: str = "INFO",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}.log"

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return an already-configured logger (call setup_logger first)."""
    return logging.getLogger(name)
