"""BeamtimeHero tool system — thin shim over `beamline_tools.cli`.

The LLM sees a single `run_command` tool (`CLI_TOOL_DEFINITION`) and walks
`beamtimehero bth --help` to discover capabilities. Dispatch happens
in-process via `beamline_tools.cli.run_cli`.
"""

from tools.definitions import CLI_TOOL_DEFINITION, TOOL_DESCRIPTIONS

__all__ = ["CLI_TOOL_DEFINITION", "TOOL_DESCRIPTIONS"]
