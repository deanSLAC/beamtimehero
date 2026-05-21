"""Per-agent-role allowlist for the BTH `beamtimehero` CLI.

Mirrors the pattern used by `autonomous/beamline_tools/agent_roles.py`:
each role declares the motors and spec-write tool names it may invoke.
The CLI wrapper in `scripts/beamtimehero` filters upstream's
`TOOL_DEFINITIONS` through this map when building the `beamtimehero bth`
branch — leaves not in the allowlist never reach argparse, so there is
no path for the agent to invoke them.

BTH never runs spec-write commands and never moves motors: both
allowlists are empty. `ref`, `tool`, and `spec-read` flow through to the
`bth` branch unchanged.
"""

from __future__ import annotations

AGENT_ROLES: dict[str, dict] = {
    "bth": {
        "motors": frozenset(),
        "spec_write_tools": frozenset(),
    },
}


def agent_motor_allowed(role: str, motor: str) -> bool:
    role_def = AGENT_ROLES.get(role)
    if role_def is None:
        return False
    return motor in role_def["motors"]


def agent_spec_write_allowed(role: str, tool_name: str) -> bool:
    role_def = AGENT_ROLES.get(role)
    if role_def is None:
        return False
    return tool_name in role_def["spec_write_tools"]
