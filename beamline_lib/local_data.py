"""Local filesystem data access -- reads SPEC data files directly via silx.

No database or pickle files required. Scans BL_SCAN_DIR for SPEC files,
parses them with silx.io.specfile.SpecFile, and caches scan metadata in a
JSON sidecar file for performance on repeated queries.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from silx.io.specfile import SpecFile, is_specfile

logger = logging.getLogger(__name__)

from bl_config import BL_SCAN_DIR

# Cache file for scan metadata (lives next to SPEC files)
_CACHE_FILE = BL_SCAN_DIR / ".scan_metadata_cache.json" if BL_SCAN_DIR else None
_metadata_cache: dict | None = None
_cache_mtime: float = 0


# ---------------------------------------------------------------------------
# SPEC file helpers
# ---------------------------------------------------------------------------

def _parse_spec_date(header_lines: list[str]) -> str | None:
    """Extract date from #D header line and return as ISO string."""
    for line in header_lines:
        if line.startswith("#D "):
            date_str = line[3:].strip()
            # SPEC date format: "Mon Apr 01 12:34:56 2024"
            for fmt in (
                "%a %b %d %H:%M:%S %Y",
                "%a %b  %d %H:%M:%S %Y",  # single-digit day with extra space
            ):
                try:
                    return datetime.strptime(date_str, fmt).isoformat()
                except ValueError:
                    continue
            # Fallback: try generic parsing
            try:
                from email.utils import parsedate_to_datetime
                return parsedate_to_datetime(date_str).isoformat()
            except Exception:
                pass
    return None


def _parse_count_time(header_lines: list[str]) -> float | None:
    """Extract count time from #T header line."""
    for line in header_lines:
        if line.startswith("#T "):
            # Format: "#T 1  (Seconds)" or "#T 0.5"
            parts = line[3:].strip().split()
            if parts:
                try:
                    return float(parts[0])
                except ValueError:
                    pass
    return None


def _parse_scan_command(header_lines: list[str]) -> tuple[int | None, str]:
    """Extract scan number and command from #S header line."""
    for line in header_lines:
        if line.startswith("#S "):
            parts = line[3:].strip().split(None, 1)
            scan_num = int(parts[0]) if parts else None
            command = parts[1] if len(parts) > 1 else ""
            return scan_num, command
    return None, ""


def _read_spec_scan(spec_path: str | Path, scan_index: int) -> pd.DataFrame | None:
    """Read a single scan from a SPEC file and return as a DataFrame.

    Returns a DataFrame with counter columns and the scan motor as the index,
    or None if the scan cannot be read.
    """
    try:
        sf = SpecFile(str(spec_path))
        scan = sf[scan_index]
        labels = scan.labels
        data = scan.data  # shape: (num_counters, num_points)

        if data.size == 0:
            return None

        df = pd.DataFrame(data.T, columns=labels)
        # Set the first column (scan motor) as index
        if labels:
            df = df.set_index(labels[0])

        # Store metadata in attrs for compatibility
        header = scan.scan_header
        date_str = _parse_spec_date(header)
        count_time = _parse_count_time(header)
        _, command = _parse_scan_command(header)

        motor_dict = {}
        try:
            motor_names = scan.motor_names
            motor_values = scan.motor_positions
            motor_dict = dict(zip(motor_names, motor_values))
        except Exception:
            pass

        # Compute timing from Epoch counter if available
        epoch_col = None
        for col in df.columns:
            if col.lower() == "epoch":
                epoch_col = col
                break

        wall_clock = None
        acquisition = None
        dead_time = None
        if count_time is not None:
            acquisition = count_time * len(df)
        if epoch_col is not None and len(df) > 1:
            epoch_vals = df[epoch_col].values.astype(float)
            wall_clock = float(epoch_vals[-1] - epoch_vals[0])
            if acquisition is not None:
                dead_time = wall_clock - acquisition

        df.attrs = {
            "date_time": datetime.fromisoformat(date_str) if date_str else None,
            "epoch": datetime.fromisoformat(date_str).timestamp() if date_str else None,
            "motor_positions": motor_dict,
            "scan_command": command,
            "counters": list(df.columns),
            "num_points": len(df),
            "count_time": count_time,
            "acquisition_seconds": acquisition,
            "wall_clock_seconds": wall_clock,
            "dead_time_seconds": dead_time,
        }
        return df
    except Exception as e:
        logger.debug("Failed to read scan %d from %s: %s", scan_index, spec_path, e)
        return None


# ---------------------------------------------------------------------------
# Scan metadata cache
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    """Load or build the scan metadata cache.

    Cache is a dict keyed by "file_name::scan_number" with metadata dicts.
    Rebuilds if the cache file is missing or older than the scan directory.
    """
    global _metadata_cache, _cache_mtime

    if _metadata_cache is not None:
        try:
            dir_mtime = BL_SCAN_DIR.stat().st_mtime if BL_SCAN_DIR.exists() else 0
        except OSError:
            dir_mtime = 0
        if dir_mtime <= _cache_mtime:
            return _metadata_cache

    # Try loading from disk
    if _CACHE_FILE and _CACHE_FILE.exists():
        try:
            _metadata_cache = json.loads(_CACHE_FILE.read_text())
            _cache_mtime = _CACHE_FILE.stat().st_mtime
            return _metadata_cache
        except (json.JSONDecodeError, OSError):
            pass

    # Build from scratch
    _metadata_cache = _build_metadata_cache()
    _save_cache()
    return _metadata_cache


def _build_metadata_cache() -> dict:
    """Scan BL_SCAN_DIR for SPEC files and extract scan metadata via silx."""
    cache = {}

    if not BL_SCAN_DIR or not BL_SCAN_DIR.exists():
        return cache

    for exp_dir in sorted(BL_SCAN_DIR.iterdir()):
        if not exp_dir.is_dir():
            continue
        for spec_path in exp_dir.iterdir():
            if not spec_path.is_file():
                continue
            try:
                if not is_specfile(str(spec_path)):
                    continue
            except Exception:
                continue

            try:
                sf = SpecFile(str(spec_path))
            except Exception:
                logger.debug("Failed to open SPEC file: %s", spec_path)
                continue

            file_name = spec_path.name
            file_mtime = spec_path.stat().st_mtime

            for scan_idx in range(len(sf)):
                try:
                    scan = sf[scan_idx]
                    header = scan.scan_header
                    scan_number = scan.number
                    _, command = _parse_scan_command(header)
                    date_str = _parse_spec_date(header)
                    count_time = _parse_count_time(header)
                    labels = scan.labels
                    data = scan.data
                    num_points = data.shape[1] if data.ndim == 2 else 0

                    motor_dict = {}
                    try:
                        motor_dict = dict(zip(scan.motor_names, scan.motor_positions))
                    except Exception:
                        pass

                    # Compute timing
                    acquisition = None
                    wall_clock = None
                    dead_time = None
                    if count_time is not None and num_points > 0:
                        acquisition = count_time * num_points
                    # Check for Epoch counter
                    if num_points > 1 and labels:
                        epoch_idx = None
                        for i, lbl in enumerate(labels):
                            if lbl.lower() == "epoch":
                                epoch_idx = i
                                break
                        if epoch_idx is not None:
                            epoch_vals = data[epoch_idx]
                            wall_clock = float(epoch_vals[-1] - epoch_vals[0])
                            if acquisition is not None:
                                dead_time = wall_clock - acquisition

                    key = f"{file_name}::{scan_number}"
                    cache[key] = {
                        "file_name": file_name,
                        "file_path": str(spec_path),
                        "experiment": exp_dir.name,
                        "scan_number": scan_number,
                        "scan_index": scan_idx,
                        "scan_command": command,
                        "date_time": date_str,
                        "epoch": datetime.fromisoformat(date_str).timestamp() if date_str else None,
                        "motor_positions": motor_dict,
                        "counters": list(labels) if labels else [],
                        "num_points": num_points,
                        "count_time": count_time,
                        "acquisition_seconds": acquisition,
                        "wall_clock_seconds": wall_clock,
                        "dead_time_seconds": dead_time,
                        "file_mtime": file_mtime,
                    }
                except Exception as e:
                    logger.debug("Failed to parse scan %d in %s: %s", scan_idx, spec_path, e)
                    continue

    return cache


def _save_cache():
    """Persist cache to disk."""
    global _cache_mtime
    if not _CACHE_FILE or not _metadata_cache:
        return
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_metadata_cache, default=str))
        _cache_mtime = _CACHE_FILE.stat().st_mtime
    except OSError as e:
        logger.warning("Failed to save metadata cache: %s", e)


def refresh_cache():
    """Force a full cache rebuild."""
    global _metadata_cache
    _metadata_cache = None
    _load_cache()


def _all_scans_sorted() -> list[dict]:
    """Return all cached scan metadata, sorted by date_time descending."""
    cache = _load_cache()
    scans = list(cache.values())
    scans.sort(key=lambda s: s.get("date_time") or "", reverse=True)
    return scans


# --- Public API ---

def list_processed_scans(limit=20) -> list[dict]:
    """List scans, most recent first."""
    scans = _all_scans_sorted()[:limit]
    return [
        {
            "file_name": s["file_name"],
            "scan_number": s["scan_number"],
            "scan_command": s["scan_command"],
            "date_time": s["date_time"],
            "num_points": s["num_points"],
            "counters": s["counters"],
            "count_time": s["count_time"],
            "acquisition_seconds": s["acquisition_seconds"],
        }
        for s in scans
    ]


def get_scan_metadata(file_name, scan_number) -> dict | None:
    """Get full metadata for a single scan."""
    cache = _load_cache()
    key = f"{file_name}::{scan_number}"
    entry = cache.get(key)
    if not entry:
        return None
    return {
        "file_name": entry["file_name"],
        "file_path": entry["file_path"],
        "scan_number": entry["scan_number"],
        "scan_command": entry["scan_command"],
        "date_time": entry["date_time"],
        "epoch": entry["epoch"],
        "motor_positions": entry["motor_positions"],
        "counters": entry["counters"],
        "num_points": entry["num_points"],
        "count_time": entry["count_time"],
        "acquisition_seconds": entry["acquisition_seconds"],
    }


def read_processed_scan(file_name, scan_number) -> pd.DataFrame | None:
    """Read scan data from the SPEC file. Returns DataFrame or None."""
    cache = _load_cache()
    key = f"{file_name}::{scan_number}"
    entry = cache.get(key)
    if not entry or not entry.get("file_path"):
        return None
    spec_path = Path(entry["file_path"])
    if not spec_path.exists():
        return None
    scan_index = entry.get("scan_index")
    if scan_index is None:
        return None
    return _read_spec_scan(spec_path, scan_index)


def get_scan_deadtime(file_name, scan_number) -> dict | None:
    """Get dead time info for a single scan."""
    cache = _load_cache()
    key = f"{file_name}::{scan_number}"
    entry = cache.get(key)
    if not entry:
        return None

    acq = entry.get("acquisition_seconds")
    wall = entry.get("wall_clock_seconds")
    dead = entry.get("dead_time_seconds")
    dead_pct = None
    if wall and dead is not None:
        dead_pct = round(100 * dead / wall, 2)

    return {
        "file_name": file_name,
        "scan_number": scan_number,
        "scan_command": entry.get("scan_command"),
        "num_points": entry.get("num_points"),
        "count_time": entry.get("count_time"),
        "acquisition_seconds": acq,
        "wall_clock_seconds": wall,
        "dead_time_seconds": dead,
        "dead_time_pct": dead_pct,
    }


def get_most_recent_file() -> str | None:
    """Find the most recently modified SPEC file (excluding alignment)."""
    for s in _all_scans_sorted():
        if s["file_name"] not in ("alignment", "alignment_Fe"):
            return s["file_name"]
    return None


def average_latest_energy_scans_file() -> str | None:
    """Find latest file with >1 energy scan. Returns file_name or None."""
    cache = _load_cache()

    file_energy_counts: dict[str, tuple[int, str]] = {}
    for entry in cache.values():
        fn = entry["file_name"]
        if fn in ("alignment", "alignment_Fe"):
            continue
        cmd = entry.get("scan_command") or ""
        if cmd.startswith("gscan energy"):
            if fn not in file_energy_counts:
                file_energy_counts[fn] = (0, "")
            count, max_dt = file_energy_counts[fn]
            dt = entry.get("date_time") or ""
            file_energy_counts[fn] = (count + 1, max(max_dt, dt))

    candidates = [(fn, count, max_dt) for fn, (count, max_dt) in file_energy_counts.items() if count > 1]
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[0][0]


def get_scan_numbers_for_file(file_name) -> list[int]:
    """Get all scan numbers for a file, sorted ascending."""
    cache = _load_cache()
    numbers = []
    for key, entry in cache.items():
        if entry["file_name"] == file_name:
            numbers.append(entry["scan_number"])
    numbers.sort()
    return numbers
