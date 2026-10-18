"""The station this deployment serves, selected by ``BTH_STATION``.

The same variable selects upstream ``beamtimehero_cli``'s station defaults
(counter priority, beam-status PVs, hidden trees, ...), so one setting
switches both layers. Unset means ``bl15`` (BL15-2), which is exactly the
pre-station behaviour.

Each station is a module in ``beamline_tools.stations`` exposing:

  NAME, BEAMLINE      station id and display name
  AGENT, SETTINGS     `claude -p --agent/--settings` for the embedded agent
  ENV_DEFAULTS        env defaults applied before any upstream import
  PROFILE             the `bth` profile (kebab leaf -> canonical path)
  REFDOCS             (name, repo-relative path, description) for `ref`
  UPSTREAM_REFDOCS    upstream bundled docs to keep listed (None = all)
  TOOL_CATEGORIES     sidebar grouping (canonical tool names)

Station content (persona prompt, reference docs) lives beside it in
``stations/<NAME>/`` and ``.claude/agents/``.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType

from dotenv import load_dotenv

# The repo's .env names the station. The server loads it too, but the CLI
# can run standalone (operator terminal), so load it here, before the
# station is chosen. Already-exported values win.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

STATIONS = ("bl15", "bl41")
DEFAULT_STATION = "bl15"


def _load() -> ModuleType:
    name = (os.environ.get("BTH_STATION") or DEFAULT_STATION).strip().lower()
    if name not in STATIONS:
        # A typo must not run one beamline with another's persona and tools.
        raise ValueError(
            f"BTH_STATION={name!r} is not a known station ({', '.join(STATIONS)})"
        )
    return importlib.import_module(f"beamline_tools.stations.{name}")


STATION: ModuleType = _load()
