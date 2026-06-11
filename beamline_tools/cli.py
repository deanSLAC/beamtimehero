"""BTH `beamtimehero` CLI: upstream parser + the `bth` agent profile.

The wrapper composes upstream's CLI helpers and registers the BTH
profile (`beamline_tools.bth_profile`). The profile is a curated view
of the master catalog whose kebab leaves alias canonical
`(tree, ..., name)` paths. Discovery: `beamtimehero --list-profiles`,
`beamtimehero bth --help`.

By default only the `ref` and `bth` trees are registered with argparse,
so canonical trees (`spec-write`, `db`, ...) cannot even be parsed by
the agent-facing binary. Operators can set `BEAMTIMEHERO_FULL_CLI=1`
to restore the full upstream catalog at a terminal. The deny rules in
`agent.settings.json` remain as a second, independent layer.

Invokable as a script via `scripts/beamtimehero`. Errors → JSON
`{"ok": false, "error": ...}` on stdout, non-zero exit. Successful tool
calls print the tool's stdout (image paths included) and exit 0.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Set env vars before any beamtimehero_cli import.
import beamline_tools.config  # noqa: F401

from beamtimehero_cli import refdocs
from beamtimehero_cli.cli.__main__ import (
    ToolParser,
    build_catalog_subtrees,
    build_profile_subtrees,
    build_ref_subtree,
    dispatch as _cli_dispatch,
    run_with,
)
from beamtimehero_cli.cli.profiles import PROFILES, register_profile
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS

from beamline_tools.bth_profile import PROFILE as _BTH_PROFILE

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_BTH_REFDOCS: list[tuple[str, str, str]] = [
    ("spec-commands", "context/BL15-2_SPEC_Reference.txt",
     "BL15-2 SPEC beamline control command reference."),
    ("user-operations", "context/BL15-2_user_reference.txt",
     "BL15-2 user operations quick reference."),
    ("cryostat-procedures", "context/cryostat_procedures.txt",
     "Liquid helium cryostat operating procedures and safety rules."),
]


_refdocs_registered = False
_profile_registered = False


def register_refdocs() -> None:
    """Idempotent: register BTH's local context docs with upstream's refdoc
    registry. Safe to call from app startup as well as the CLI builder."""
    global _refdocs_registered
    if _refdocs_registered:
        return
    for name, rel_path, description in _BTH_REFDOCS:
        refdocs.register_doc(name, PROJECT_ROOT / rel_path, description)
    _refdocs_registered = True


def _register_bth_profile() -> None:
    global _profile_registered
    if _profile_registered:
        return
    register_profile(_BTH_PROFILE)
    _profile_registered = True


def _full_cli_enabled() -> bool:
    """Operator escape hatch: expose the full upstream catalog trees."""
    return os.environ.get("BEAMTIMEHERO_FULL_CLI") == "1"


def build_parser():
    register_refdocs()
    _register_bth_profile()
    parser = ToolParser(
        prog="beamtimehero",
        description=(
            "BTH-scoped beamtimehero CLI. The `bth` profile lists every "
            "command the BeamtimeHero agent is allowed to run."
        ),
    )
    parser.add_argument(
        "--list-profiles", action="store_true", dest="list_profiles",
        help="List registered agent profiles and their alias counts.",
    )
    trees = parser.add_subparsers(dest="tree", metavar="<tree>")
    build_ref_subtree(trees)
    # Canonical trees (incl. spec-write/db) are operator-only: without the
    # env flag they are never registered, so the agent-facing binary cannot
    # even parse them. agent.settings.json deny rules are the second layer.
    if _full_cli_enabled():
        build_catalog_subtrees(trees, TOOL_DEFINITIONS)
        build_profile_subtrees(trees, TOOL_DEFINITIONS)
        return parser

    # build_profile_subtrees iterates upstream's global PROFILES registry
    # (which auto-discovers built-ins like bl-aligner). Restrict it to bth
    # for the duration of the build so future upstream profiles can't
    # silently widen the agent-facing surface — then restore it, since a
    # permanent prune would truncate the registry for any other in-process
    # consumer.
    others = {n: p for n, p in PROFILES.items() if n != _BTH_PROFILE["name"]}
    for name in others:
        del PROFILES[name]
    try:
        build_profile_subtrees(trees, TOOL_DEFINITIONS)
    finally:
        PROFILES.update(others)
    return parser


_CATALOG_TREES = frozenset({
    "tool", "db", "spec-read", "spec-write", "spec-file", "s3df", "slack",
})


def _known_trees() -> frozenset[str]:
    base = frozenset({"ref", _BTH_PROFILE["name"]})
    return base | _CATALOG_TREES if _full_cli_enabled() else base


def main(argv: list[str] | None = None) -> int:
    if _full_cli_enabled():
        return run_with(build_parser, _cli_dispatch, argv, known_trees=_known_trees())
    # Hide non-bth profiles for the whole invocation (parse AND dispatch),
    # so `--list-profiles` doesn't advertise profiles the parser won't
    # accept. build_parser() does the same prune/restore internally for
    # in-process callers; the dict operations nest cleanly.
    others = {n: p for n, p in PROFILES.items() if n != _BTH_PROFILE["name"]}
    for name in others:
        del PROFILES[name]
    try:
        return run_with(build_parser, _cli_dispatch, argv, known_trees=_known_trees())
    finally:
        PROFILES.update(others)


if __name__ == "__main__":
    sys.exit(main())
