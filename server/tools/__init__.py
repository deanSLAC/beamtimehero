"""BeamtimeHero tool system.

Provides beamline data tools via two strategies:
- MCP: Full tool schemas in API payload (native function-calling)
- CLI: Single run_command tool with progressive discovery
"""

from tools.definitions import TOOL_DEFINITIONS, CLI_TOOL_DEFINITION
from tools.executor import execute_tool
