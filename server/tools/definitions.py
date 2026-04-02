"""Tool definitions for BeamtimeHero.

TOOL_DEFINITIONS: Full schemas for MCP mode (10 tools).
CLI_TOOL_DEFINITION: Single run_command tool for CLI mode.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_latest_scan",
            "description": "Get the most recently processed scan. Returns metadata and a data preview.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scans",
            "description": "List processed scans with metadata (file name, scan number, command, counters, number of points).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of scans to list (default 20)",
                        "default": 20,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_scan",
            "description": "Read a processed scan's data and metadata. Use list_scans first to find available file_name and scan_number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The SPEC source file name"},
                    "scan_number": {"type": "integer", "description": "The scan number within the file"},
                },
                "required": ["file_name", "scan_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_log_entries",
            "description": "Get the most recent entries from the beamline control logs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to return (default 100)",
                        "default": 100,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Search the beamline control logs for a specific string or error message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The text to search for in logs"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50)",
                        "default": 50,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_logs",
            "description": "List available log files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of logs to list (default 20)",
                        "default": 20,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_counter",
            "description": "Identify the 'active' fluorescence/absorption counter for a scan. Logic: ppboff if present, else the vortDT/vortDT2/vortDT3/vortDT4 with highest max counts, else I1.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The SPEC source file name"},
                    "scan_number": {"type": "integer", "description": "The scan number within the file"},
                },
                "required": ["file_name", "scan_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scan_deadtime",
            "description": "Get the dead time for a scan — the overhead time spent on motor moves, settling, and communication vs actual detector acquisition. Returns wall-clock duration, acquisition time, dead time in seconds, and dead time as a percentage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The SPEC source file name"},
                    "scan_number": {"type": "integer", "description": "The scan number within the file"},
                },
                "required": ["file_name", "scan_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_scan",
            "description": "Generate and display a plot of scan data. Use this by default when the user wants to see a plot. The plot is shown directly to the user. Use list_scans to find available file_name and scan_number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "The SPEC source file name"},
                    "scan_number": {"type": "integer", "description": "The scan number within the file"},
                    "counter": {
                        "type": "string",
                        "description": "Counter to plot (e.g. 'I0', 'vortDT'). If omitted, auto-detects the active counter.",
                    },
                    "normalize_by": {
                        "type": "string",
                        "description": "Optional counter to normalize by (e.g. 'I0')",
                    },
                },
                "required": ["file_name", "scan_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_data",
            "description": "General-purpose plotting tool. Plot any data as a line chart. Use this to visualize results from other tools (e.g. read_scan). Supports multiple series on one plot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "X-axis values.",
                    },
                    "y": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Y-axis values (same length as x).",
                    },
                    "y2": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Optional second series Y values.",
                    },
                    "y3": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Optional third series Y values.",
                    },
                    "y4": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Optional fourth series Y values.",
                    },
                    "xlabel": {"type": "string", "description": "X-axis label."},
                    "ylabel": {"type": "string", "description": "Y-axis label."},
                    "title": {"type": "string", "description": "Plot title."},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Legend labels for each series.",
                    },
                },
                "required": ["x", "y"],
            },
        },
    },
]

# Single tool definition for CLI mode
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
