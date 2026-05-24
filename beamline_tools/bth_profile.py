"""BTH agent profile — curated CLI surface for the BeamtimeHero web chat agent.

Each kebab leaf maps to the canonical ``(tree, ..., name)`` path in
``beamtimehero_cli``'s master tool catalog. Registered with the upstream
profile mechanism by ``beamline_tools.cli``; surfaces as the top-level
``beamtimehero bth`` branch.
"""
from __future__ import annotations

PROFILE = {
    "name": "bth",
    "description": "BeamtimeHero web-chat agent surface (file-cache SPEC data, read-only).",
    "aliases": {
        # ---- Scan data + analysis + plots (file-cache backend) ----------
        "list-scans":                ("spec-file", "list_scans"),
        "get-latest-scan":           ("spec-file", "get_latest_scan"),
        "read-scan":                 ("spec-file", "read_scan"),
        "get-active-counter":        ("spec-file", "get_active_counter"),
        "get-scan-deadtime":         ("spec-file", "get_scan_deadtime"),
        "normalize-scan":            ("spec-file", "normalize_scan"),
        "average-scans":             ("spec-file", "average_scans"),
        "plot-scan":                 ("spec-file", "plot_scan"),
        "plot-averaged-scans":       ("spec-file", "plot_averaged_scans"),
        "plot-scan-stack":           ("spec-file", "plot_scan_stack"),
        "plot-first-half-vs-second-half": ("spec-file", "plot_first_half_vs_second_half"),
        "plot-running-average":      ("spec-file", "plot_running_average"),
        "plot-feature-evolution":    ("spec-file", "plot_feature_evolution"),
        "group-scans-by-spot":       ("spec-file", "group_scans_by_spot"),
        "analyze-per-spot":          ("spec-file", "analyze_per_spot"),
        "analyze-convergence":       ("spec-file", "analyze_convergence"),
        "analyze-efficiency":        ("spec-file", "analyze_efficiency"),
        "analyze-feature-evolution": ("spec-file", "analyze_feature_evolution"),

        # ---- Logs (canonical 'tool' tree) -------------------------------
        "get-latest-log-entries":    ("tool", "get_latest_log_entries"),
        "search-logs":               ("tool", "search_logs"),
        "list-logs":                 ("tool", "list_logs"),

        # ---- Files, macros, generic plot, eval, configs ('tool') --------
        "list-files":                ("tool", "list_files"),
        "read-file":                 ("tool", "read_file"),
        "write-summary":             ("tool", "write_summary"),
        "write-macro":               ("tool", "write_macro"),
        "save-plan":                 ("tool", "save_plan"),
        "plot-data":                 ("tool", "plot_data"),
        "evaluate-spec-macro":       ("tool", "evaluate_spec_macro"),
        "get-motor-config":          ("tool", "get_motor_config"),
        "get-counter-config":        ("tool", "get_counter_config"),

        # ---- SPEC read-only state ---------------------------------------
        "read-motor-position":       ("spec-read", "read_motor_position"),
        "read-all-positions":        ("spec-read", "read_all_positions"),
        "get-beam-size":             ("spec-read", "get_beam_size"),
        "get-beam-status":           ("spec-read", "get_beam_status"),
        "get-counts":                ("spec-read", "get_counts"),
        "get-counter":               ("spec-read", "get_counter"),
        "get-element":               ("spec-read", "get_element"),
        "get-scan-number":           ("spec-read", "get_scan_number"),
        "get-current-datafile":      ("spec-read", "get_current_datafile"),
        "get-plotselected-counter":  ("spec-read", "get_plotselected_counter"),
        "get-anchor":                ("spec-read", "get_anchor"),

        # ---- Action log query (db tree) ---------------------------------
        "recent-actions":            ("db", "recent_actions"),
    },
}
