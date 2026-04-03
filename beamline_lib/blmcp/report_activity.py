"""Standalone activity report data generator — outputs JSON to stdout.

Returns scan summary and beam stability data for a configurable time window.
Plots are handled by separate tools (plot_activity, plot_counter_timeseries).

Usage: python3 blmcp/report_activity.py [hours]
  hours: Number of hours to look back (default 24)
"""

import json
import os
import sys
import traceback

def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from blmcp.tools import get_activity_summary, get_beam_stability

    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24

    result = {}

    try:
        result["summary"] = get_activity_summary(hours=hours)
    except Exception:
        result["summary_error"] = traceback.format_exc()

    try:
        result["beam_stability"] = get_beam_stability(hours=hours)
    except Exception:
        result["beam_stability_error"] = traceback.format_exc()

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"fatal_error": traceback.format_exc()}, indent=2))
