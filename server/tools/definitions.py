"""Tool definitions for BeamtimeHero.

CLI_TOOL_DEFINITION: The single `run_command` tool sent to the LLM. The model
discovers actual capabilities by invoking `beamtimehero --help` and friends.

TOOL_DESCRIPTIONS: snake_case name → one-line description, used only by the
frontend sidebar. Not sent to the LLM.
"""

TOOL_DESCRIPTIONS = {
    "get_latest_scan": "Get the most recently processed scan with metadata and data preview",
    "list_scans": "List processed scans with metadata",
    "read_scan": "Read a processed scan's data and metadata",
    "get_latest_log_entries": "Get the most recent entries from beamline control logs",
    "search_logs": "Search beamline control logs for a string or error message",
    "list_logs": "List available log files",
    "get_active_counter": "Identify the active fluorescence/absorption counter for a scan",
    "get_scan_deadtime": "Get dead time (overhead) for a scan",
    "normalize_scan": "Edge-step normalize a scan (divide by I0, then scale pre/post edge)",
    "average_scans": "Average all energy scans in a SPEC file after edge-step normalization",
    "analyze_convergence": "Check if repeated scans have converged (cosine similarity metrics)",
    "analyze_efficiency": "Full scan repetition efficiency report: convergence, CV, optimal count, verdict",
    "plot_scan": "Generate a plot of scan data",
    "plot_averaged_scans": "Plot averaged energy scans for multiple samples overlaid",
    "plot_data": "General-purpose line chart from data arrays",
    "list_files": "List non-SPEC files in the scan directory (macros, configs, etc.)",
    "read_file": "Read a text file from the scan directory",
    "write_summary": "Save a conversation summary as a .txt file in the scan directory",
    "write_macro": "Save an edited macro as a new .mac file in the scan directory",
    "get_motor_config": "Get SPEC motor configuration (controller, steps, mnemonic, name)",
    "get_counter_config": "Get SPEC counter configuration (controller, channel, mnemonic, name)",
    "spec_command": "Send a command to the running SPEC session (whitelisted commands only)",
}

CLI_TOOL_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a beamtimehero CLI command to query beamline data, logs, and plots. "
                "Start with 'beamtimehero --help' to discover available commands. "
                "Use 'beamtimehero <command> --help' to see options for a specific command."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The full CLI command string to execute (e.g. 'beamtimehero list-scans --limit 5')",
                    }
                },
                "required": ["command"],
            },
        },
    },
]
