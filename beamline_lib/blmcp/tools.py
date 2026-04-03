"""MCP tool implementations -- thin wrappers around bldata_analysis."""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from bldata_analysis import scans, logs, plotting
from config import BL_SCAN_DIR


# ---- Scan data tools ----

def list_scans(limit=20):
    return scans.list_processed_scans(limit=limit)


def get_latest_scan():
    results = scans.list_processed_scans(limit=1)
    if not results:
        return None
    entry = results[0]
    df = scans.read_processed_scan(entry["file_name"], entry["scan_number"])
    if df is not None:
        entry["data_preview"] = df.head(10).to_string()
        entry["counters"] = list(df.columns)
    return entry


def read_scan(file_name, scan_number):
    meta = scans.get_scan_metadata(file_name, scan_number)
    if not meta:
        return None
    df = scans.read_processed_scan(file_name, scan_number)
    if df is not None:
        meta["data"] = df.to_string()
    return meta


def get_activity_summary(hours=24):
    return scans.get_activity_summary(hours=hours)


def get_scan_deadtime(file_name, scan_number):
    return scans.get_scan_deadtime(file_name, scan_number)


def get_active_counter(file_name, scan_number):
    return scans.get_active_counter(file_name, scan_number)


def edge_step_normalize_scan(file_name, scan_number, counter=None, normalize_by="I0"):
    return scans.edge_step_normalize_scan(file_name, scan_number, counter=counter, normalize_by=normalize_by)


def average_energy_scans(file_name=None):
    return scans.average_energy_scans(file_name=file_name)


def analyze_scan_convergence(file_name=None):
    """Analyze scan convergence using cosine similarity metrics."""
    from blmcp.cosine_similarity_tool import analyze_scan_quality

    try:
        combined, file_name, counter, used_scans = scans.get_normalized_scan_arrays(file_name)
    except ValueError as e:
        return {"error": str(e)}

    if len(used_scans) < 2:
        return {"error": f"Need at least 2 scans for convergence analysis, found {len(used_scans)}."}

    scan_data_2d = combined.dropna().values.T.tolist()
    result = analyze_scan_quality(scan_data_2d)

    if "error" in result:
        return result

    result["file_name"] = file_name
    result["active_counter"] = counter
    result["scan_numbers"] = used_scans
    return result


def analyze_scan_efficiency(file_name=None):
    """Comprehensive scan repetition efficiency report."""
    from blmcp.scan_efficiency_tool import analyze_scan_efficiency as _analyze

    try:
        combined, file_name, counter, used_scans = scans.get_normalized_scan_arrays(file_name)
    except ValueError as e:
        return {"error": str(e)}

    if len(used_scans) < 2:
        return {"error": f"Need at least 2 scans for efficiency analysis, found {len(used_scans)}."}

    scan_data_2d = combined.dropna().values.T.tolist()
    result = _analyze(scan_data_2d)

    if "error" in result:
        return result

    result["file_name"] = file_name
    result["active_counter"] = counter
    result["scan_numbers"] = used_scans
    return result


def average_latest_energy_scans():
    return scans.average_latest_energy_scans()


def get_beam_stability(hours=24):
    return scans.get_beam_stability(hours=hours)


def list_logs(limit=20):
    return logs.list_logs(limit=limit)


def get_latest_log_entries(lines=100):
    return logs.get_latest_log_entries(lines=lines)


def search_logs(query, max_results=50):
    return logs.search_logs(query, max_results=max_results)


# ---- Plot tools ----

def plot_scan(file_name, scan_number, counter=None, normalize_by=None):
    """Generate a scan plot for display. Returns (fig, summary) or (None, error)."""
    return plotting.plot_scan(file_name, scan_number, counter=counter, normalize_by=normalize_by)


def plot_counter_timeseries(counter_name, hours=24):
    """Plot a counter time series across scans. Returns (fig, summary)."""
    return plotting.plot_counter_timeseries(counter_name, hours=hours)


def plot_activity(hours=24):
    """Plot beamline activity timeline. Returns (fig, summary)."""
    return plotting.plot_activity(hours=hours)


def plot_averaged_scans_overlay(file_names):
    """Plot averaged energy scans for multiple samples. Returns (fig, summary)."""
    return plotting.plot_averaged_scans_overlay(file_names)


def analyze_scan_plot(file_name, scan_number, counter=None, normalize_by=None):
    """Generate a scan plot for LLM visual analysis. Returns (fig, base64, summary) or (None, None, error)."""
    fig, summary = plotting.plot_scan(file_name, scan_number, counter=counter, normalize_by=normalize_by)
    if fig is None:
        return None, None, summary
    b64 = plotting.fig_to_base64(fig)
    return fig, b64, summary


# ---- Log command/error query tools ----

def get_commands_between_timestamps(start, end):
    """Get SPEC commands issued between two timestamps (ISO format)."""
    from datetime import datetime
    import local_data
    start_dt = datetime.fromisoformat(start) if isinstance(start, str) else start
    end_dt = datetime.fromisoformat(end) if isinstance(end, str) else end
    return local_data.get_commands_between_timestamps(start_dt, end_dt)


def get_commands_between_scans(scan1_file, scan1_number, scan2_file, scan2_number):
    """Get commands issued between two scans by looking up their timestamps."""
    import local_data
    meta1 = scans.get_scan_metadata(scan1_file, scan1_number)
    meta2 = scans.get_scan_metadata(scan2_file, scan2_number)
    if not meta1 or not meta2:
        return {"error": "One or both scans not found in metadata."}
    t1 = meta1.get("date_time")
    t2 = meta2.get("date_time")
    if not t1 or not t2:
        return {"error": "Scans found but missing timestamps."}
    start_dt, end_dt = sorted([t1, t2])
    from datetime import datetime
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)
    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)
    return local_data.get_commands_between_timestamps(start_dt, end_dt)


def get_recent_log_errors(hours=24):
    """Get recent errors detected in SPEC logs."""
    import local_data
    return local_data.get_recent_errors(hours=hours)


def get_commands_for_logfile(log_file, limit=100):
    """Get commands from a specific log file."""
    import local_data
    return local_data.get_commands_for_logfile(log_file, limit=limit)
