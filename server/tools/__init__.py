"""BeamtimeHero tool system.

The LLM sees a single `run_command` tool (CLI_TOOL_DEFINITION) and discovers
capabilities by walking the `beamtimehero` argparse CLI. Tool implementations
are dispatched by execute_tool. TOOL_DESCRIPTIONS is a flat name → description
map used only by the frontend sidebar.
"""

from tools.definitions import CLI_TOOL_DEFINITION, TOOL_DESCRIPTIONS
from tools.executor import execute_tool
