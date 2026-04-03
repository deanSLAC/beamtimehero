"""Scan data operations -- reads SPEC files directly via silx.

Uses local_data module for metadata queries and scan reading.
No pickle files required.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from config import BL_SCAN_DIR, now_pacific
import local_data


def list_processed_scans(limit=20):
    """List scans, most recent first."""
    return local_data.list_processed_scans(limit=limit)


def get_scan_metadata(file_name, scan_number):
    """Get full metadata for a single scan."""
    return local_data.get_scan_metadata(file_name, scan_number)


def read_processed_scan(file_name, scan_number):
    """Read scan data from the SPEC file. Returns DataFrame or None."""
    return local_data.read_processed_scan(file_name, scan_number)


def get_scan_deadtime(file_name, scan_number):
    """Get dead time info for a single scan."""
    return local_data.get_scan_deadtime(file_name, scan_number)


def get_activity_summary(hours=24):
    """Generate a summary of beamline activity over a configurable time window."""
    return local_data.get_activity_summary(hours=hours)


def get_active_counter(file_name, scan_number):
    """Determine the 'active' fluorescence/absorption counter for a scan.

    Decision logic:
      1. If 'ppboff' is a counter, it is the active counter.
      2. Else if 'vortDT' is a counter, compare max values of vortDT, vortDT2,
         vortDT3, vortDT4 -- whichever has the highest max is active.
      3. Otherwise, default to 'I1'.
    """
    df = read_processed_scan(file_name, scan_number)
    if df is None:
        return None

    cols = set(df.columns)

    if "ppboff" in cols:
        return {
            "file_name": file_name,
            "scan_number": scan_number,
            "active_counter": "ppboff",
            "reason": "ppboff counter present",
        }

    vort_candidates = ["vortDT", "vortDT2", "vortDT3", "vortDT4"]
    available_vorts = [c for c in vort_candidates if c in cols]
    if available_vorts:
        best = max(available_vorts, key=lambda c: df[c].max())
        return {
            "file_name": file_name,
            "scan_number": scan_number,
            "active_counter": best,
            "reason": f"highest max among {available_vorts}",
        }

    return {
        "file_name": file_name,
        "scan_number": scan_number,
        "active_counter": "I1",
        "reason": "no ppboff or vortDT counters, defaulting to I1",
    }


def _edge_step_normalize(df, counter, normalize_by="I0"):
    """Core edge-step normalization on a scan DataFrame."""
    if counter not in df.columns:
        raise KeyError(f"Counter '{counter}' not found. Available: {list(df.columns)}")
    if normalize_by and normalize_by not in df.columns:
        raise KeyError(f"Normalization counter '{normalize_by}' not found. Available: {list(df.columns)}")

    energy = df.index.values.astype(float)
    signal = df[counter].values.astype(float)

    if normalize_by:
        i0 = df[normalize_by].values.astype(float)
        i0_safe = np.where(i0 == 0, 1.0, i0)
        signal = signal / i0_safe

    n = len(signal)
    n10 = max(1, n // 10)
    pre_mean = np.mean(signal[:n10])
    post_mean = np.mean(signal[-n10:])
    denom = post_mean - pre_mean
    if abs(denom) < 1e-15:
        normalized = signal - pre_mean
    else:
        normalized = (signal - pre_mean) / denom

    return energy, normalized


def edge_step_normalize_scan(file_name, scan_number, counter=None, normalize_by="I0"):
    """Load a scan, normalize by I0, then apply edge-step normalization."""
    df = read_processed_scan(file_name, scan_number)
    if df is None:
        return None

    if counter is None:
        active = get_active_counter(file_name, scan_number)
        if active is None:
            return None
        counter = active["active_counter"]

    try:
        energy, normalized = _edge_step_normalize(df, counter, normalize_by)
    except KeyError as e:
        return {"error": str(e)}

    result_df = pd.DataFrame({"energy": energy, "normalized": normalized})
    result_df = result_df.set_index("energy")

    return {
        "file_name": file_name,
        "scan_number": scan_number,
        "counter": counter,
        "normalize_by": normalize_by,
        "num_points": len(result_df),
        "data": result_df.to_string(),
    }


def get_most_recent_file():
    """Find the most recently modified SPEC file (excluding alignment)."""
    return local_data.get_most_recent_file()


def get_normalized_scan_arrays(file_name=None):
    """Load all scans for a file, normalize, and return as a DataFrame on a common energy grid."""
    if file_name is None:
        file_name = get_most_recent_file()
        if file_name is None:
            raise ValueError("No SPEC files found.")

    scan_numbers = local_data.get_scan_numbers_for_file(file_name)

    if not scan_numbers:
        raise ValueError(f"No scans found for file '{file_name}'.")

    active = get_active_counter(file_name, scan_numbers[0])
    if active is None:
        raise ValueError(f"Could not load scan data for '{file_name}' scan {scan_numbers[0]}.")
    counter = active["active_counter"]

    normalized_scans = []
    used_scans = []
    for sn in scan_numbers:
        df = read_processed_scan(file_name, sn)
        if df is None:
            continue
        try:
            energy, norm = _edge_step_normalize(df, counter, normalize_by="I0")
        except KeyError:
            continue
        normalized_scans.append(pd.Series(norm, index=energy, name=f"S{sn:03d}"))
        used_scans.append(sn)

    if not normalized_scans:
        raise ValueError(f"No valid scans to normalize in '{file_name}'.")

    combined = pd.concat(normalized_scans, axis=1)
    return combined, file_name, counter, used_scans


def average_energy_scans(file_name=None):
    """Average all energy scans in a SPEC file after edge-step normalization."""
    try:
        combined, file_name, counter, used_scans = get_normalized_scan_arrays(file_name)
    except ValueError as e:
        return {"error": str(e)}

    avg = combined.mean(axis=1)
    std = combined.std(axis=1)

    result_df = pd.DataFrame({"energy": avg.index, "average": avg.values, "std": std.values})
    result_df = result_df.set_index("energy")

    return {
        "file_name": file_name,
        "active_counter": counter,
        "num_scans_averaged": len(used_scans),
        "scan_numbers": used_scans,
        "num_points": len(result_df),
        "data": result_df.to_string(),
    }


def average_latest_energy_scans():
    """Find the latest file with >1 energy-motor scan and return the average."""
    file_name = local_data.average_latest_energy_scans_file()
    if not file_name:
        return {"error": "No file found with more than 1 energy scan."}
    return average_energy_scans(file_name=file_name)


def find_scans_in_timeframe(start_time, end_time):
    """Find all scans within a time window."""
    return local_data.find_scans_in_timeframe(start_time, end_time)


def _find_column_ci(df, name):
    """Find a column name in a DataFrame using case-insensitive matching."""
    name_lower = name.lower()
    for col in df.columns:
        if col.lower() == name_lower:
            return col
    return None


def build_counter_timeseries(start_time, end_time, counter_name, exclude_files=None):
    """Build a time series of a counter across all scans in a time window."""
    scan_entries = find_scans_in_timeframe(start_time, end_time)
    timeseries = []

    for entry in scan_entries:
        if exclude_files and entry["file_name"] in exclude_files:
            continue
        df = local_data.read_processed_scan(entry["file_name"], entry["scan_number"])
        if df is None:
            continue

        actual_col = _find_column_ci(df, counter_name)
        if actual_col is None:
            continue

        motor_positions = df.attrs.get("motor_positions", {})
        filter_pos = motor_positions.get("filter")

        values = df[actual_col].values.astype(float)
        point_time = entry["date_time"]
        dt_str = point_time.isoformat() if hasattr(point_time, 'isoformat') else str(point_time)

        for val in values:
            timeseries.append({
                "datetime": dt_str,
                "file_name": entry["file_name"],
                "scan_number": entry["scan_number"],
                "value": float(val),
                "filter_position": filter_pos,
            })

    return timeseries


def get_beam_stability(hours=24):
    """Analyze SPEAR beam uptime and I0 stability over a time window."""
    end_time = now_pacific()
    start_time = end_time - timedelta(hours=hours)

    # --- SPEAR analysis ---
    spear_ts = build_counter_timeseries(start_time, end_time, "SPEAR")

    spear_values = [p["value"] for p in spear_ts]
    spear_events = []
    total_points = len(spear_values)
    normal_points = 0
    missing_fill_points = 0
    beam_lost_points = 0

    if spear_values:
        for p in spear_ts:
            val = p["value"]
            if val >= 490:
                normal_points += 1
            elif val >= 10:
                missing_fill_points += 1
            else:
                beam_lost_points += 1

        in_event = False
        event_start = None
        event_type = None
        for p in spear_ts:
            val = p["value"]
            if val < 490 and not in_event:
                in_event = True
                event_start = p["datetime"]
                event_type = "beam_lost" if val < 10 else "missing_fills"
            elif val >= 495 and in_event:
                spear_events.append({
                    "type": event_type,
                    "start": event_start,
                    "recovered_at": p["datetime"],
                    "file_name": p["file_name"],
                })
                in_event = False
                event_type = None

        if in_event:
            spear_events.append({
                "type": event_type,
                "start": event_start,
                "recovered_at": None,
                "file_name": spear_ts[-1]["file_name"],
            })

    spear_analysis = {
        "total_data_points": total_points,
        "normal_points": normal_points,
        "normal_pct": round(100 * normal_points / total_points, 2) if total_points else 0,
        "missing_fill_points": missing_fill_points,
        "beam_lost_points": beam_lost_points,
        "events": spear_events,
        "mean_current_mA": round(float(np.mean(spear_values)), 2) if spear_values else None,
    }

    # --- I0 analysis ---
    i0_ts = build_counter_timeseries(start_time, end_time, "I0", exclude_files=["alignment"])

    filter_groups = {}
    for p in i0_ts:
        fp = p.get("filter_position")
        if fp not in filter_groups:
            filter_groups[fp] = []
        filter_groups[fp].append(p)

    per_filter_group = []
    primary_filter = None
    primary_count = 0
    for fp, points in sorted(filter_groups.items(), key=lambda x: (x[0] is None, x[0])):
        vals = np.array([p["value"] for p in points])

        file_buckets = {}
        for p in points:
            fn = p["file_name"]
            if fn not in file_buckets:
                file_buckets[fn] = []
            file_buckets[fn].append(p["value"])

        files = []
        for fn, fvals in sorted(file_buckets.items()):
            farr = np.array(fvals)
            files.append({
                "file_name": fn,
                "num_points": len(farr),
                "mean": round(float(farr.mean()), 2),
                "std": round(float(farr.std()), 2),
                "cv_pct": round(100 * float(farr.std() / farr.mean()), 2) if farr.mean() != 0 else None,
            })

        group = {
            "filter_position": fp,
            "num_points": len(vals),
            "mean": round(float(vals.mean()), 2),
            "std": round(float(vals.std()), 2),
            "cv_pct": round(100 * float(vals.std() / vals.mean()), 2) if vals.mean() != 0 else None,
            "min": round(float(vals.min()), 2),
            "max": round(float(vals.max()), 2),
            "files": files,
        }
        per_filter_group.append(group)

        if len(vals) > primary_count:
            primary_count = len(vals)
            primary_filter = group

    i0_analysis = {
        "filter_position": primary_filter["filter_position"] if primary_filter else None,
        "num_points": primary_filter["num_points"] if primary_filter else 0,
        "mean": primary_filter["mean"] if primary_filter else None,
        "std": primary_filter["std"] if primary_filter else None,
        "cv_pct": primary_filter["cv_pct"] if primary_filter else None,
        "min": primary_filter["min"] if primary_filter else None,
        "max": primary_filter["max"] if primary_filter else None,
        "num_filter_settings_total": len(filter_groups),
    }

    return {
        "window_start": start_time.isoformat(),
        "window_end": end_time.isoformat(),
        "hours": hours,
        "spear_analysis": spear_analysis,
        "i0_analysis": i0_analysis,
    }


def get_activity_data(hours=24):
    """Build 10-minute resolution activity bins for a time window."""
    return local_data.get_activity_data(hours=hours)
