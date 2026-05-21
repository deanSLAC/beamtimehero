"""Tool descriptions for the BeamtimeHero frontend sidebar.

TOOL_DESCRIPTIONS: snake_case name → one-line description, derived from
upstream's `TOOL_DEFINITIONS` filtered through the bth allowlist. The
agent itself discovers and invokes tools via Bash against
`./scripts/beamtimehero bth …` — see `.claude/agents/beamline-bth.md`.
This map is read-only metadata for the UI.
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
