"""Plotting functions for processed scan data."""

import io
import base64
import logging

logger = logging.getLogger(__name__)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import scans


def plot_scan(file_name, scan_number, counter=None, normalize_by=None):
    """Plot a processed scan and return the figure + text summary.

    If counter is not specified, auto-detects the active counter.

    Returns:
        (fig, summary) — matplotlib Figure and a text description of the plot.
        Returns (None, error_message) if the scan can't be loaded.
    """
    df = scans.read_processed_scan(file_name, scan_number)
    if df is None:
        return None, f"Scan not found: {file_name} #{scan_number}"

    # Auto-detect active counter when none specified
    if not counter:
        active = scans.get_active_counter(file_name, scan_number)
        if active:
            counter = active["active_counter"]

    meta = scans.get_scan_metadata(file_name, scan_number)

    fig, ax = plt.subplots(figsize=(8, 5))

    x_label = df.index.name or "index"

    if counter:
        if counter not in df.columns:
            available = list(df.columns)
            plt.close(fig)
            return None, f"Counter '{counter}' not found. Available: {available}"
        y = df[counter]
        if normalize_by:
            if normalize_by not in df.columns:
                plt.close(fig)
                return None, f"Normalization counter '{normalize_by}' not found."
            y = y / df[normalize_by]
            y_label = f"{counter}/{normalize_by}"
        else:
            y_label = counter
        ax.plot(df.index, y)
        ax.set_ylabel(y_label)
    else:
        for col in df.columns:
            ax.plot(df.index, df[col], label=col)
        ax.legend(fontsize=8)
        y_label = "counts"

    ax.set_xlabel(x_label)

    title = f"{file_name} scan #{scan_number}"
    if meta and meta.get("scan_command"):
        title += f"\n{meta['scan_command']}"
    ax.set_title(title, fontsize=10)

    fig.tight_layout()

    # Build text summary
    parts = [
        f"Plot of {file_name} scan #{scan_number}",
        f"X axis: {x_label} ({len(df)} points)",
    ]
    if counter:
        parts.append(f"Y axis: {y_label}")
        parts.append(f"Range: {float(y.min()):.4g} to {float(y.max()):.4g}")
    else:
        parts.append(f"Counters plotted: {list(df.columns)}")
    if meta and meta.get("scan_command"):
        parts.append(f"Command: {meta['scan_command']}")

    summary = ". ".join(parts) + "."
    return fig, summary


def plot_counter_timeseries(counter_name, hours=24, exclude_files=None):
    """Plot a counter as a time series across all scans in a time window.

    Uses build_counter_timeseries to gather per-point data from SPEC files,
    then plots value vs scan index, color-coded by file_name.

    Args:
        counter_name: Counter to plot (e.g. "I0", "SPEAR"). Case-insensitive.
        hours: Number of hours to look back (default 24).
        exclude_files: Optional list of file names to exclude.

    Returns:
        (fig, summary) — matplotlib Figure and text summary.
        Returns (None, error_message) if no data found.
    """
    from datetime import timedelta
    from config import now_pacific

    end_time = now_pacific()
    start_time = end_time - timedelta(hours=hours)

    ts = scans.build_counter_timeseries(start_time, end_time, counter_name, exclude_files=exclude_files)

    if not ts:
        return None, f"No '{counter_name}' data found in the past {hours} hours."

    # Group points by file_name for color coding
    file_groups = {}
    for p in ts:
        fn = p["file_name"]
        if fn not in file_groups:
            file_groups[fn] = []
        file_groups[fn].append(p)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Plot each file as a separate series with sequential x-index
    idx = 0
    tick_positions = []
    tick_labels = []
    for fn, points in file_groups.items():
        x = list(range(idx, idx + len(points)))
        y = [p["value"] for p in points]
        ax.plot(x, y, '.', markersize=3, label=fn, alpha=0.7)
        # Mark file boundary with a tick at the midpoint
        mid = idx + len(points) // 2
        tick_positions.append(mid)
        tick_labels.append(fn)
        idx += len(points)

    ax.set_ylabel(counter_name)
    ax.set_xlabel("File / Scan sequence")
    ax.set_title(f"{counter_name} over past {hours}h ({start_time.strftime('%m/%d %H:%M')} – {end_time.strftime('%m/%d %H:%M')})", fontsize=10)

    # Show file names as x-ticks if not too many
    if len(tick_positions) <= 15:
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha="right", fontsize=7)
    else:
        ax.legend(fontsize=6, ncol=2, loc="upper left")

    fig.tight_layout()

    # Summary
    all_values = [p["value"] for p in ts]
    import numpy as np
    vals = np.array(all_values)
    parts = [
        f"Time series of {counter_name} over the past {hours} hours",
        f"{len(ts)} data points across {len(file_groups)} file(s)",
        f"Mean: {vals.mean():.2f}, Std: {vals.std():.2f}",
        f"Range: {vals.min():.2f} to {vals.max():.2f}",
    ]
    summary = ". ".join(parts) + "."
    return fig, summary


def plot_activity(hours=24):
    """Plot beamline activity as a binary timeline at 10-minute resolution.

    Green shading = active (scan running), white = inactive.

    Returns:
        (fig, summary) or (None, error_message).
    """
    from datetime import datetime

    data = scans.get_activity_data(hours=hours)
    if not data or not data["bins"]:
        return None, f"No scan data found in the past {hours} hours."

    bins = data["bins"]
    times = [datetime.fromisoformat(b["start"]) for b in bins]
    values = [b["active"] for b in bins]

    fig, ax = plt.subplots(figsize=(12, 2.5))

    import matplotlib.dates as mdates

    ax.fill_between(times, values, step="post", alpha=0.6, color="#2ecc71")
    ax.step(times, values, where="post", color="#27ae60", linewidth=0.8)

    ax.set_ylim(-0.1, 1.4)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Inactive", "Active"])
    ax.set_xlabel("Time")
    ax.set_title(
        f"Beamline Activity — past {hours}h "
        f"({data['active_pct']}% active, {data['total_scans']} scans)",
        fontsize=10,
    )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    fig.autofmt_xdate(rotation=30, ha="right")
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()

    summary = (
        f"Beamline activity over the past {hours} hours. "
        f"{data['active_bins']} of {data['total_bins']} bins active ({data['active_pct']}%). "
        f"{data['total_scans']} total scans. "
        f"Window: {data['window_start']} to {data['window_end']}."
    )
    return fig, summary


def plot_averaged_scans_overlay(file_names):
    """Plot edge-step-normalized averaged energy scans for multiple samples.

    Each sample is plotted as a separate line on the same axes.
    Alignment files are skipped.

    Args:
        file_names: List of SPEC file names (one per sample).

    Returns:
        (fig, summary) or (None, error_message).
    """
    import numpy as np

    skip = {"alignment", "alignment_Fe"}
    sample_names = [fn for fn in file_names if fn not in skip]

    if not sample_names:
        return None, "No non-alignment samples to plot."

    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = []

    import pandas as pd

    for fn in sample_names:
        result = scans.average_energy_scans(file_name=fn)
        if not result or "error" in result:
            logger.info("Skipping %s: %s", fn, result.get("error") if result else "no result")
            continue
        # Parse the string data back into arrays for plotting
        lines = result["data"].strip().split("\n")
        energies, averages, stds = [], [], []
        for line in lines[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 2:
                energies.append(float(parts[0]))
                averages.append(float(parts[1]))
                stds.append(float(parts[2]) if len(parts) >= 3 else 0.0)
        if not energies:
            continue
        energies_arr = np.array(energies)
        avg_arr = np.array(averages)
        std_arr = np.array(stds)
        label = f"{fn} ({result['num_scans_averaged']} scans)"
        line, = ax.plot(energies_arr, avg_arr, label=label, linewidth=1.2)
        if std_arr.any():
            ax.fill_between(energies_arr, avg_arr - std_arr, avg_arr + std_arr,
                            alpha=0.15, color=line.get_color())
        plotted.append(fn)

    if not plotted:
        plt.close(fig)
        return None, "No valid averaged scans to plot."

    ax.set_xlabel("Energy (eV)")
    ax.set_ylabel("Normalized absorption")
    ax.set_title("Averaged Energy Scans — Past 24h Samples", fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    summary = (
        f"Overlay of averaged energy scans for {len(plotted)} sample(s): "
        f"{', '.join(plotted)}."
    )
    return fig, summary


def fig_to_base64(fig):
    """Convert a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
