"""Guard the bth profile surface against silent upstream drift.

Upstream's build_profile_subtrees skips aliases whose canonical path no
longer exists in the catalog with only a log warning — an upstream tool
rename would silently shrink the agent's tool surface. These tests fail
loudly instead.
"""
import beamline_tools.config  # noqa: F401 — env defaults before upstream import

from beamline_tools.bth_profile import PROFILE
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS
from beamtimehero_cli.tool_catalog.categorize import categorize


def _catalog_paths() -> set[tuple]:
    paths = set()
    for tdef in TOOL_DEFINITIONS:
        name = (tdef.get("function") or {}).get("name")
        if name:
            paths.add(categorize(tdef) + (name,))
    return paths


def test_every_alias_resolves_to_a_catalog_tool():
    paths = _catalog_paths()
    missing = {
        alias: tuple(canonical)
        for alias, canonical in PROFILE["aliases"].items()
        if tuple(canonical) not in paths
    }
    assert not missing, (
        f"bth profile aliases no longer resolve (upstream rename?): {missing}"
    )


def test_sidebar_descriptions_cover_the_full_profile():
    from tools import TOOL_DESCRIPTIONS

    assert len(TOOL_DESCRIPTIONS) == len(PROFILE["aliases"]), (
        "sidebar TOOL_DESCRIPTIONS dropped aliases — an upstream tool was "
        "renamed or two aliases collided on a canonical name"
    )
