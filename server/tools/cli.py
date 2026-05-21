"""Server-side shim over `beamline_tools.cli`.

Kept so existing callers (`server/conversation.py`, `server/api_client.py`)
do not have to know about the `beamline_tools` package layout. New code
should import directly from `beamline_tools.cli`.
"""
from __future__ import annotations

import beamline_tools.config  # noqa: F401 — set env before upstream import

from beamline_tools.cli import run_cli  # noqa: F401

# Context files that always stay in the system prompt (vs. served on-demand
# via `beamtimehero bth ref <doc>`).
ALWAYS_IN_PROMPT: frozenset[str] = frozenset({
    "system_prompt.txt",
    "experiment_modes.txt",
})
