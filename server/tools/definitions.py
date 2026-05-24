"""Tool descriptions for the BeamtimeHero frontend sidebar.

`TOOL_DESCRIPTIONS`: snake_case canonical name → one-line description,
derived from upstream tool defs reached via the `bth` profile's aliases.
Each alias points at a canonical `(tree, ..., name)` path in
`beamtimehero_cli.tool_catalog.TOOL_DEFINITIONS`; we index that catalog
and pull the description for every reachable alias. The agent itself
discovers and invokes tools via Bash against `./scripts/beamtimehero
bth <leaf>` — see `.claude/agents/beamline-bth.md`. This map is
read-only metadata for the UI.
"""
from __future__ import annotations

import beamline_tools.config  # noqa: F401 — set env before upstream import

from beamline_tools.bth_profile import PROFILE as _BTH_PROFILE
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS
from beamtimehero_cli.tool_catalog.categorize import categorize


def _build_descriptions() -> dict[str, str]:
    # Index tool defs by canonical (tree, ..., name) — the shape profile
    # aliases use. Two defs can share a name (e.g. spec-file/list_scans
    # vs s3df/list_scans); the tree disambiguates.
    by_path: dict[tuple[str, ...], dict] = {}
    for tdef in TOOL_DEFINITIONS:
        name = (tdef.get("function") or {}).get("name")
        if not name:
            continue
        by_path[categorize(tdef) + (name,)] = tdef

    out: dict[str, str] = {}
    for _alias, canonical in (_BTH_PROFILE.get("aliases") or {}).items():
        tdef = by_path.get(tuple(canonical))
        if tdef is None:
            continue
        fn = tdef.get("function") or {}
        name = fn.get("name")
        desc = (fn.get("description") or "").strip().split("\n", 1)[0]
        if name:
            out[name] = desc
    return out


TOOL_DESCRIPTIONS: dict[str, str] = _build_descriptions()
