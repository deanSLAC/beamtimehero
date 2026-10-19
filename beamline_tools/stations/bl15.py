"""BL15-2 station: agent persona, `bth` profile, reference docs, UI.

The default station (``BTH_STATION`` unset). Everything here is what
BeamtimeHero was before stations existed; change it only for BL15-2.

``PROFILE`` maps each kebab leaf to the canonical ``(tree, ..., name)``
path in ``beamtimehero_cli``'s master tool catalog. Registered with the
upstream profile mechanism by ``beamline_tools.cli``; surfaces as the
top-level ``beamtimehero bth`` branch.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

NAME = "bl15"
BEAMLINE = "SSRL BL15-2"

# `claude -p --agent <AGENT> --settings <SETTINGS>` (paths relative to the repo)
AGENT = "beamline-bth"
SETTINGS = "agent.settings.json"

# Env defaults applied (setdefault) before any beamtimehero_cli import.
# BL15-2 talks to its live SPEC session via GNU screen; BL_SCAN_DIR /
# BL_LOGS_DIR come from the host's .env.
ENV_DEFAULTS: dict[str, str] = {
    "SPEC_MOCK": "0",
    "SPEC_TRANSPORT": "screen",
    "BEAMTIMEHERO_DATA_DIR": str(_ROOT / "data"),
    "BEAMTIMEHERO_LOG_DIR": str(_ROOT / "logs"),
    "BEAMTIMEHERO_SUGGESTIONS_DIR": str(_ROOT / "user_suggestions"),
    # save-plan target (upstream documents ./logs/plans/)
    "BEAMTIMEHERO_PLANS_DIR": str(_ROOT / "logs" / "plans"),
}

# (name, path relative to repo, description) for `beamtimehero ref`.
REFDOCS: list[tuple[str, str, str]] = [
    ("spec-commands", "stations/bl15/context/BL15-2_SPEC_Reference.txt",
     "BL15-2 SPEC beamline control command reference."),
    ("user-operations", "stations/bl15/context/BL15-2_user_reference.txt",
     "BL15-2 user operations quick reference."),
    ("cryostat-procedures", "stations/bl15/context/cryostat_procedures.txt",
     "Liquid helium cryostat operating procedures and safety rules."),
]

# Upstream's bundled refdocs to keep listed; None keeps all of them.
UPSTREAM_REFDOCS: tuple[str, ...] | None = None

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

# Sidebar category order + membership (canonical tool names). Tools not
# listed here fall under "Other".
TOOL_CATEGORIES = [
    (
        "Scan Data & Analysis",
        [
            "get_latest_scan", "list_scans", "read_scan",
            "get_active_counter", "get_scan_deadtime",
            "normalize_scan", "average_scans",
            "analyze_convergence", "analyze_efficiency",
            "analyze_feature_evolution", "analyze_per_spot",
            "group_scans_by_spot",
        ],
    ),
    (
        "Plots",
        [
            "plot_scan", "plot_averaged_scans", "plot_data",
            "plot_scan_stack", "plot_first_half_vs_second_half",
            "plot_running_average", "plot_feature_evolution",
        ],
    ),
    (
        "Beamline Logs",
        ["get_latest_log_entries", "search_logs", "list_logs"],
    ),
    (
        "Files & Macros",
        [
            "list_files", "read_file", "write_summary",
            "write_macro", "evaluate_spec_macro", "save_plan",
        ],
    ),
    (
        "SPEC State (read-only)",
        [
            "get_motor_config", "get_counter_config",
            "read_all_positions", "read_motor_position",
            "get_current_datafile", "get_scan_number",
            "get_beam_status", "get_beam_size",
            "get_counts", "get_counter",
            "get_element", "get_anchor", "get_plotselected_counter",
        ],
    ),
]

# Sidebar "Try asking" prompts; empty hides the box. None yet: examples
# must be run against this station's agent and data before listing them.
EXAMPLE_PROMPTS: list[str] = []
