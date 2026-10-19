"""BTH config: set the station's env defaults, then re-export upstream config.

Must be imported *before* any `beamtimehero_cli` module: upstream
`beamtimehero_cli.config` reads `SPEC_MOCK`, `SPEC_TRANSPORT`,
`BL_SCAN_DIR`, `BL_LOGS_DIR`, and `BEAMTIMEHERO_DATA_DIR` at module-import
time, so changing them after the first upstream import has no effect.

Defaults come from the station module (`beamline_tools.station`); values
already in the environment (the host's .env) win.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from beamline_tools.station import STATION  # noqa: E402

# BTH runs on the beamline computer talking to a live SPEC session.
# Upstream defaults to mock, so override before importing.
for _k, _v in STATION.ENV_DEFAULTS.items():
    os.environ.setdefault(_k, _v)

from beamtimehero_cli import config as _upstream  # noqa: E402

# Where agent notes (write_summary, write_macro, save_plan) go when no
# YYYY-mm_* experiment dir resolved: BL_SCAN_DIR is then the bare data
# root (e.g. /fourone), which must not collect stray files.
_NOTES_FALLBACK = Path(os.environ["BEAMTIMEHERO_LOG_DIR"])
_notes_dir = (_upstream.BL_SCAN_DIR if _upstream.SCAN_DIR_CONFIGURED
              else _NOTES_FALLBACK)

# Upstream's save_plan imports config.PLANS_DIR, which upstream never
# defines. BEAMTIMEHERO_PLANS_DIR (station default, .env wins) names it;
# "{scan_dir}" is the active experiment directory as this process resolved
# it, so plans follow !setdir like write_summary does.
_upstream.PLANS_DIR = Path(
    os.environ["BEAMTIMEHERO_PLANS_DIR"].format(scan_dir=_notes_dir)
)
if "{scan_dir}" not in os.environ["BEAMTIMEHERO_PLANS_DIR"]:
    _upstream.PLANS_DIR.mkdir(parents=True, exist_ok=True)

if not _upstream.SCAN_DIR_CONFIGURED:
    # local_data.write_file writes into BL_SCAN_DIR; point it at the
    # fallback for the write only, so readers still see "not configured".
    from beamtimehero_cli.spec_data import local_data as _local_data

    _upstream_write_file = _local_data.write_file

    def _write_file_to_fallback(filename: str, content: str) -> str:
        scan_dir = _upstream.BL_SCAN_DIR
        _upstream.BL_SCAN_DIR = _NOTES_FALLBACK
        try:
            return str(_NOTES_FALLBACK / _upstream_write_file(filename, content))
        finally:
            _upstream.BL_SCAN_DIR = scan_dir

    _local_data.write_file = _write_file_to_fallback

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
