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
BL_SCAN_DIR = Path(os.getenv("BL_SCAN_DIR", "/sdf/group/ssrl/isaac/data/data"))
BL_LOGS_DIR = Path(os.getenv("BL_LOGS_DIR", "/sdf/group/ssrl/isaac/data/logs"))

# Local development fallbacks
if not BL_SCAN_DIR.exists():
    BL_SCAN_DIR = Path(__file__).parent / "sample_data"
if not BL_LOGS_DIR.exists():
    BL_LOGS_DIR = Path(__file__).parent / "sample_data"

# File patterns
LOG_FILE_PATTERN = "log__*"

# Limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_LOG_LINES = 1000
