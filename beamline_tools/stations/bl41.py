"""BL4-1 station: agent persona, `bth` profile, reference docs, UI.

Selected by ``BTH_STATION=bl41`` (which also selects upstream
beamtimehero_cli's BL4-1 defaults: counter priority xsum/xsA/xsB/I1,
BL04:State, 67 s count cap, xrs/tender trees hidden).

The profile follows autonomous_fourone's read-only chat surface
(``beamline_tools/agent_roles.py`` ``_CHAT_TOOLS``), plus read-only SPEC
state queries. Strictly read-only by enumeration: no file, macro, DB,
Slack or SPEC writes. Left out on purpose:

  write_summary, write_macro, save_plan, record_energy_calibration,
  record_provenance, export_results_bundle   writers
  get_counts, get_counter                    run `ct` (cscan box + shutter)
  evaluate_spec_macro                        executes SPEC code (sandbox)
  get_anchor, get_beam_size, get_element     BL15-2 macros
  capture_sample_image                       no BL4-1 camera yet
  research/ask_question                      off-host research agent
  cherfd_wait_for_scan                       blocks a chat turn until a sweep ends
  cherfd_get_undulator/daq_status            BL15-2 only

cherfd-read leaves are GET-only REST calls to the cscan (cherfd) server.
"""
from __future__ import annotations

NAME = "bl41"
BEAMLINE = "SSRL BL4-1"

# `claude -p --agent <AGENT> --settings <SETTINGS>` (paths relative to the repo)
AGENT = "beamline-bth-bl41"
SETTINGS = "agent.settings.bl41.json"

# Run root on the data disk, like /fourone/<app>/{data,logs} for the other
# BL4-1 apps.
_RUN_ROOT = "/fourone/beamtimehero"

# Env defaults applied (setdefault) before any beamtimehero_cli import.
ENV_DEFAULTS: dict[str, str] = {
    "SPEC_MOCK": "0",
    # SPEC server mode (spec -S 2033), as autonomous_fourone uses. Never
    # screen: stuffing keystrokes into the session would type into
    # whatever the user is running.
    "SPEC_TRANSPORT": "tcp",
    "SPEC_HOST": "localhost",
    "SPEC_PORT": "2033",
    # newest /fourone/YYYY-MM_* is picked; staff override with !setdir
    "BL_SCAN_DIR": "/fourone",
    "BL_LOGS_DIR": "/usr/local/lib/spec.log/logfiles",
    "BEAMTIMEHERO_DATA_DIR": f"{_RUN_ROOT}/data",
    "BEAMTIMEHERO_LOG_DIR": f"{_RUN_ROOT}/logs",
    "BEAMTIMEHERO_SUGGESTIONS_DIR": f"{_RUN_ROOT}/user_suggestions",
    # cherfd-read tools talk to the live cscan server (GET only); upstream
    # mocks it unless CHERFD_MOCK is exactly "0"
    "CHERFD_MOCK": "0",
    "CHERFD_SERVER_URL": "http://127.0.0.1:5002",
    # upstream's bl41 default names autonomous_fourone's logs in its repo;
    # it writes them under its run root
    "BTH_APP_LOG_ROOTS": (
        "fourone=/fourone/autonomous_fourone/logs,"
        "microagents=/usr/local/projects/autonomous_microagents/logs,"
        "cherfd=/usr/local/projects/cherfd_claude/logs,"
        "cscan_acq=/usr/local/projects/cscan_acq/logs,"
        "xsp32=/usr/local/projects/xspress_32element/logs,"
        "motor_analyzer=/usr/local/projects/motor_analyzer/logs,"
        "current_amps=/usr/local/projects/ssrl-current-amp/logs"
    ),
}

PROFILE = {
    "name": "bth",
    "description": "BeamtimeHero BL4-1 web-chat agent surface (read-only).",
    "aliases": {
        # ---- Scan data ---------------------------------------------------
        "list-scans":                ("spec-file", "list_scans"),
        "get-latest-scan":           ("spec-file", "get_latest_scan"),
        "read-scan":                 ("spec-file", "read_scan"),
        "get-active-counter":        ("spec-file", "get_active_counter"),
        "get-scan-deadtime":         ("spec-file", "get_scan_deadtime"),
        "group-scans-by-spot":       ("spec-file", "group_scans_by_spot"),

        # ---- XAS reduction + analysis -----------------------------------
        "normalize-scan":            ("spec-file", "normalize_scan"),
        "average-scans":             ("spec-file", "average_scans"),
        "identify-edge":             ("spec-file", "identify_edge"),
        "find-edge-e0":              ("spec-file", "find_edge_e0"),
        "get-energy-calibration":    ("spec-file", "get_energy_calibration"),
        "normalize-xas-intensity":   ("spec-file", "normalize_xas_intensity"),
        "fit-xas-pre-edge":          ("spec-file", "fit_xas_pre_edge"),
        "fit-xas-white-line":        ("spec-file", "fit_xas_white_line"),
        "extract-xas-descriptors":   ("spec-file", "extract_xas_descriptors"),
        "interpret-oxidation-state": ("spec-file", "interpret_oxidation_state"),
        "interpret-coordination-geometry": ("spec-file", "interpret_coordination_geometry"),
        "summarize-sample-chemistry": ("spec-file", "summarize_sample_chemistry"),
        "compare-xas-to-references": ("spec-file", "compare_xas_to_references"),
        "align-spectra":             ("spec-file", "align_spectra"),
        "difference-spectrum":       ("spec-file", "difference_spectrum"),

        # ---- Data quality + convergence ---------------------------------
        "assess-xas-quality":        ("spec-file", "assess_xas_quality"),
        "detect-per-scan-drift":     ("spec-file", "detect_per_scan_drift"),
        "analyze-convergence":       ("spec-file", "analyze_convergence"),
        "analyze-efficiency":        ("spec-file", "analyze_efficiency"),
        "analyze-feature-evolution": ("spec-file", "analyze_feature_evolution"),
        "analyze-per-spot":          ("spec-file", "analyze_per_spot"),

        # ---- Plots (written to the chat's session plot dir) -------------
        "plot-scan":                 ("spec-file", "plot_scan"),
        "plot-averaged-scans":       ("spec-file", "plot_averaged_scans"),
        "plot-scan-stack":           ("spec-file", "plot_scan_stack"),
        "plot-first-half-vs-second-half": ("spec-file", "plot_first_half_vs_second_half"),
        "plot-running-average":      ("spec-file", "plot_running_average"),
        "plot-feature-evolution":    ("spec-file", "plot_feature_evolution"),
        "plot-data":                 ("tool", "plot_data"),

        # ---- EXAFS -------------------------------------------------------
        "list-collector-scans":      ("exafs", "list_collector_scans"),
        "extract-chi":               ("exafs", "extract_chi"),
        "fourier-transform-chi":     ("exafs", "fourier_transform_chi"),
        "exafs-products":            ("exafs", "exafs_products"),
        "overlay-chi-spectra":       ("exafs", "overlay_chi_spectra"),

        # ---- Logs --------------------------------------------------------
        "get-latest-log-entries":    ("tool", "get_latest_log_entries"),
        "search-logs":               ("tool", "search_logs"),
        "list-logs":                 ("tool", "list_logs"),
        "list-app-logs":             ("tool", "list_app_logs"),
        "read-app-log":              ("tool", "read_app_log"),
        "search-app-logs":           ("tool", "search_app_logs"),

        # ---- Files + SPEC config (read) ---------------------------------
        "list-files":                ("tool", "list_files"),
        "read-file":                 ("tool", "read_file"),
        "get-motor-config":          ("tool", "get_motor_config"),
        "get-counter-config":        ("tool", "get_counter_config"),

        # ---- Station services + EPICS (HTTP GET / caget only) -----------
        "caget":                     ("tool", "caget"),
        "get-sample-environment":    ("tool", "get_sample_environment"),
        "get-ge-detector-status":    ("tool", "get_ge_detector_status"),
        "get-motor-diagnostics":     ("tool", "get_motor_diagnostics"),

        # ---- SPEC read-only state (SPEC server, no motion/counting) -----
        "read-motor-position":       ("spec-read", "read_motor_position"),
        "read-all-positions":        ("spec-read", "read_all_positions"),
        "get-beam-status":           ("spec-read", "get_beam_status"),
        "get-check-beam":            ("spec-read", "get_check_beam"),
        "get-crystal-set":           ("spec-read", "get_crystal_set"),
        "get-scan-number":           ("spec-read", "get_scan_number"),
        "get-current-datafile":      ("spec-read", "get_current_datafile"),
        "get-plotselected-counter":  ("spec-read", "get_plotselected_counter"),

        # ---- Continuous scans: cscan / cherfd server (GET only) ---------
        "cherfd-get-status":         ("cherfd-read", "cherfd_get_status"),
        "cherfd-get-scan-results":   ("cherfd-read", "cherfd_get_scan_results"),
        "cherfd-check-readiness":    ("cherfd-read", "cherfd_check_readiness"),
        "cherfd-check-command":      ("cherfd-read", "cherfd_check_command"),
        "cherfd-get-table-tracking": ("cherfd-read", "cherfd_get_table_tracking"),
        "cherfd-get-server-settings": ("cherfd-read", "cherfd_get_server_settings"),
        "cherfd-get-station":        ("cherfd-read", "cherfd_get_station"),

        # ---- This agent's own action log --------------------------------
        "recent-actions":            ("db", "recent_actions"),
    },
}

_CTX = "stations/bl41/context"

# (name, path relative to repo, description) for `beamtimehero ref`.
REFDOCS: list[tuple[str, str, str]] = [
    ("beamline-overview", f"{_CTX}/beamline-overview.md",
     "BL4-1 at a glance: wiggler XAS/EXAFS, mono crystal sets A/B and energy "
     "ranges, detectors and counters, data directories, which signal to use."),
    ("spec-commands", f"{_CTX}/spec-commands.md",
     "BL4-1 SPEC command reference: motors, counting, gscan/kscan, mono and "
     "crystal set, shutter, check_beam, darks, amplifier gains."),
    ("user-operations", f"{_CTX}/user-operations.md",
     "A typical BL4-1 user session start to finish, where to go for what, "
     "when to call staff."),
    ("web-apps", f"{_CTX}/web-apps.md",
     "BL4-1 web apps and services (cscan, detector GUI, gas mixer, ...): "
     "URL/port, purpose, user-facing or staff-only."),
    ("sample-alignment", f"{_CTX}/sample-alignment.md",
     "Aligning a sample in the beam at BL4-1."),
    ("changing-energy", f"{_CTX}/changing-energy.md",
     "Moving to a new edge: crystal set, mono, slits, gains, darks; what "
     "staff do versus users."),
    ("energy-calibration", f"{_CTX}/energy-calibration.md",
     "Reference-foil energy calibration, E0 conventions, calibrate_mono."),
    ("data-collection", f"{_CTX}/data-collection.md",
     "Collecting XANES/EXAFS: continuous (cscan, default) vs step scans, "
     "count times, reps, transmission vs fluorescence, linear count window."),
    ("data-quality", f"{_CTX}/data-quality.md",
     "Judging data: convergence and when to stop, sample damage, glitches, "
     "detector saturation and dead time, edge jump."),
    ("exafs-reduction", f"{_CTX}/exafs-reduction.md",
     "How chi(k)/FT EXAFS reduction is done here and what the outputs mean."),
    ("cryostat-procedures", f"{_CTX}/cryostat-procedures.md",
     "BL4-1 cryostat operating procedures and safety rules."),
    ("ge-detector", f"{_CTX}/ge-detector.md",
     "The 24-element Ge (Xspress) detector: xsum/xsA/xsB/xsNN, ROIs, dead "
     "time, saturation, common problems."),
    ("current-amplifiers", f"{_CTX}/current-amplifiers.md",
     "SR570 amplifiers on I0/I1/I2/pips: gains, offsets, linear window, darks."),
    ("gas-ionchambers", f"{_CTX}/gas-ionchambers.md",
     "Ion chamber gas fills and high voltage; the gas mixer app."),
    ("epics-pvs", f"{_CTX}/epics-pvs.md",
     "Useful read-only EPICS PVs for caget at BL4-1 (beam, amps, detector, "
     "mono, sample environment)."),
    ("glossary", f"{_CTX}/glossary.md", "BL4-1 terms and abbreviations."),
]

# Upstream's bundled refdocs that are useful to a BL4-1 user-facing agent;
# the rest are developer docs.
UPSTREAM_REFDOCS: tuple[str, ...] | None = ("counter-selection", "cherfd-data-format")

# Sidebar category order + membership (canonical tool names). Tools not
# listed here fall under "Other".
TOOL_CATEGORIES = [
    (
        "Scan Data",
        [
            "list_scans", "get_latest_scan", "read_scan",
            "get_active_counter", "get_scan_deadtime", "group_scans_by_spot",
        ],
    ),
    (
        "XAS Analysis",
        [
            "normalize_scan", "average_scans", "identify_edge", "find_edge_e0",
            "get_energy_calibration", "normalize_xas_intensity",
            "fit_xas_pre_edge", "fit_xas_white_line", "extract_xas_descriptors",
            "interpret_oxidation_state", "interpret_coordination_geometry",
            "summarize_sample_chemistry", "compare_xas_to_references",
            "align_spectra", "difference_spectrum",
        ],
    ),
    (
        "Data Quality",
        [
            "assess_xas_quality", "detect_per_scan_drift",
            "analyze_convergence", "analyze_efficiency",
            "analyze_feature_evolution", "analyze_per_spot",
        ],
    ),
    (
        "EXAFS",
        [
            "list_collector_scans", "extract_chi", "fourier_transform_chi",
            "exafs_products", "overlay_chi_spectra",
        ],
    ),
    (
        "Plots",
        [
            "plot_scan", "plot_averaged_scans", "plot_scan_stack",
            "plot_first_half_vs_second_half", "plot_running_average",
            "plot_feature_evolution", "plot_data",
        ],
    ),
    (
        "Continuous Scans (cscan)",
        [
            "cherfd_get_status", "cherfd_get_scan_results",
            "cherfd_check_readiness", "cherfd_check_command",
            "cherfd_get_table_tracking", "cherfd_get_server_settings",
            "cherfd_get_station",
        ],
    ),
    (
        "Logs",
        [
            "get_latest_log_entries", "search_logs", "list_logs",
            "list_app_logs", "read_app_log", "search_app_logs",
        ],
    ),
    (
        "Beamline State (read-only)",
        [
            "get_beam_status", "get_check_beam", "get_crystal_set",
            "read_all_positions", "read_motor_position",
            "get_current_datafile", "get_scan_number", "get_plotselected_counter",
            "caget", "get_sample_environment", "get_ge_detector_status",
            "get_motor_diagnostics", "get_motor_config", "get_counter_config",
        ],
    ),
    (
        "Files",
        ["list_files", "read_file", "recent_actions"],
    ),
]

# Sidebar "Try asking" prompts (click fills the chat box). Each was run
# through the agent against real BL4-1 data/services and exercises the
# tools above; re-check them when the profile changes. Not listed: averaging,
# convergence and chi(k)/FT prompts. Those tools read SPEC step scans only,
# not cscan sweeps (BL4-1's default), so they fail on typical user data.
EXAMPLE_PROMPTS: list[str] = [
    "Plot my latest scan and tell me whether the data look good.",
    "What edge am I measuring, and where is E0?",
    "Is there drift or sample damage across my scans?",
    "Show me the results of my last cscan sweep.",
    "Were there any errors or warnings in the SPEC log in the last hour?",
    "Is the beam up, and is the Ge detector dead time OK?",
    "Is the cscan server ready for my next scan?",
]
