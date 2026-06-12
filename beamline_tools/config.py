"""BTH config: set env defaults, then re-export upstream config.

Must be imported *before* any `beamtimehero_cli` module: upstream
`beamtimehero_cli.config` reads `SPEC_MOCK`, `SPEC_TRANSPORT`,
`BL_SCAN_DIR`, `BL_LOGS_DIR`, and `BEAMTIMEHERO_DATA_DIR` at module-import
time, so changing them after the first upstream import has no effect.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# BTH runs on the beamline computer talking to a live SPEC session via GNU
# screen. Upstream defaults to mock + tcp, so override before importing.
os.environ.setdefault("SPEC_MOCK", "0")
os.environ.setdefault("SPEC_TRANSPORT", "screen")
os.environ.setdefault("BEAMTIMEHERO_DATA_DIR", str(PROJECT_ROOT / "data"))

# BTH runs on the beamline computer, where serving packaged demo data as if
# it were live would mislead users. Disable upstream's sample-data fallback
# by default: an unconfigured BL_SCAN_DIR/BL_LOGS_DIR then surfaces as "not
# configured" (and tools report no data) instead of silently returning demo
# scans. Operators can set BEAMTIMEHERO_NO_SAMPLE_FALLBACK=0 to re-enable the
# fallback for a local UI demo.
os.environ.setdefault("BEAMTIMEHERO_NO_SAMPLE_FALLBACK", "1")

# BL_SCAN_DIR / BL_LOGS_DIR come from the beamline host's .env; do not
# override here.

from beamtimehero_cli import config as _upstream  # noqa: E402

# Re-export the values BTH code reads. Attribute access through the
# upstream module keeps live mutations (set_scan_dir) visible.
BL_TIMEZONE = _upstream.BL_TIMEZONE
now_pacific = _upstream.now_pacific
set_scan_dir = _upstream.set_scan_dir


def get_scan_dir() -> Path:
    """Current BL_SCAN_DIR (re-read each call so set_scan_dir is visible)."""
    return _upstream.BL_SCAN_DIR


def get_logs_dir() -> Path:
    return _upstream.BL_LOGS_DIR


def scan_dir_configured() -> bool:
    """True when BL_SCAN_DIR points at a real, existing beamline scan dir."""
    return _upstream.SCAN_DIR_CONFIGURED


def logs_dir_configured() -> bool:
    """True when BL_LOGS_DIR points at a real, existing log directory."""
    return _upstream.LOGS_DIR_CONFIGURED
