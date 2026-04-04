"""Shared configuration for BL15-2 beamline tools."""

import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BL_TIMEZONE = ZoneInfo("America/Los_Angeles")


def now_pacific() -> datetime:
    """Return current time in Pacific, as a naive datetime for comparison."""
    return datetime.now(BL_TIMEZONE).replace(tzinfo=None)

from dotenv import load_dotenv

load_dotenv()

# Data directories
BL_LOGS_DIR = Path(os.getenv("BL_LOGS_DIR", "/usr/local/lib/spec.log/logfiles"))
if not BL_LOGS_DIR.exists():
    BL_LOGS_DIR = Path(__file__).parent / "sample_data"


def _resolve_scan_dir(root: Path) -> Path:
    """Pick the most recently modified subdirectory, or fall back to sample_data."""
    if root.is_dir():
        subdirs = [d for d in root.iterdir() if d.is_dir()]
        if subdirs:
            return max(subdirs, key=lambda d: d.stat().st_mtime)
    return Path(__file__).parent / "sample_data"


_DATA_ROOT = Path(os.getenv("BL_SCAN_DIR", "/data/fifteen"))
BL_SCAN_DIR = _resolve_scan_dir(_DATA_ROOT)

# File patterns
LOG_FILE_PATTERN = "log__*"

# Limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_LOG_LINES = 1000
