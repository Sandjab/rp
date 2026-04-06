"""Shared logging and configuration utilities for the RP pipeline."""

import logging
import os
import sys
from pathlib import Path

import yaml

# ── Path constants ────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent.parent
PIPELINE_DIR = PROJECT_DIR / ".pipeline"
SCRIPTS_DIR = PROJECT_DIR / "scripts"
CONFIG_DIR = PROJECT_DIR / "config"

# ── Logging ───────────────────────────────────────────────────────────────────

_MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB


def setup_logging(name: str) -> logging.Logger:
    """Configure and return a logger for the given script name.

    Checks RP_DEBUG env var:
    - Normal mode: INFO level, bare format (identical to print(stderr))
    - Debug mode:  DEBUG level, timestamped format + file handler to .pipeline/debug.log
    """
    debug = os.environ.get("RP_DEBUG", "").strip() not in ("", "0")
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Stderr handler — always present
    stderr_handler = logging.StreamHandler(sys.stderr)
    if debug:
        stderr_handler.setLevel(logging.DEBUG)
        stderr_handler.setFormatter(
            logging.Formatter("[%(asctime)s %(name)s %(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )
    else:
        stderr_handler.setLevel(logging.INFO)
        stderr_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stderr_handler)

    # File handler — debug mode only
    if debug:
        try:
            PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
            log_path = PIPELINE_DIR / "debug.log"

            # Truncate if too large
            if log_path.exists() and log_path.stat().st_size > _MAX_LOG_SIZE:
                log_path.write_text("")

            file_handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter("[%(asctime)s %(name)s %(levelname)s] %(message)s",
                                  datefmt="%Y-%m-%d %H:%M:%S")
            )
            logger.addHandler(file_handler)
        except OSError:
            logger.warning("Could not create debug log file in .pipeline/")

    return logger


# ── Configuration ─────────────────────────────────────────────────────────────


def load_config() -> dict:
    """Load the main config from config/revue-presse.yaml."""
    config_path = CONFIG_DIR / "revue-presse.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
