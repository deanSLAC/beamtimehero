"""Tool definitions for BeamtimeHero.

CLI_TOOL_DEFINITION: the single `run_command` tool sent to the LLM. The
model discovers actual capabilities by walking `beamtimehero bth --help`
and friends.

TOOL_DESCRIPTIONS: snake_case name → one-line description, derived from
upstream's `TOOL_DEFINITIONS` filtered through the bth allowlist. Used
only by the frontend sidebar.
"""
from __future__ import annotations

import beamline_tools.config  # noqa: F401 — set env before upstream import

from beamline_tools.cli import bth_tool_definitions


def _build_descriptions() -> dict[str, str]:
    out: dict[str, str] = {}
    for tdef in bth_tool_definitions():
        fn = tdef.get("function") or {}
        name = fn.get("name")
        if not name:
            continue
        desc = (fn.get("description") or "").strip().split("\n", 1)[0]
        out[name] = desc
    return out


TOOL_DESCRIPTIONS: dict[str, str] = _build_descriptions()

CLI_TOOL_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run a `beamtimehero bth ...` CLI command. "
                "Start with `beamtimehero bth --help` to see the subtrees "
                "(ref, tool, spec-read). Then `beamtimehero bth <subtree> "
                "--help` for the available commands, and `beamtimehero bth "
                "<subtree> <command> --help` for the flags."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "The full CLI command string to execute (e.g. "
                            "'beamtimehero bth tool list-scans --limit 5')"
                        ),
                    }
                },
                "required": ["command"],
            },
        },
    },
]
