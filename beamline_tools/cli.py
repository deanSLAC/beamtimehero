"""BTH `beamtimehero` CLI: upstream parser + the `bth` agent branch.

The wrapper exposes a single top-level branch — `bth` — whose subtrees
(`ref`, `tool`, `spec-read`) come from upstream after filtering through
`beamline_tools.agent_roles.AGENT_ROLES["bth"]`. The allowlists are
empty, so every spec-write leaf is dropped before argparse ever sees it.

Importable from the server (`run_cli(...)`) and invokable as a script
via `scripts/beamtimehero`. Errors → JSON `{"ok": false, "error": ...}`
on stdout, non-zero exit. Successful tool calls print the tool's stdout
(image paths included) and exit 0.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shlex
import sys
from pathlib import Path

# Set env vars before any beamtimehero_cli import.
import beamline_tools.config  # noqa: F401

from beamtimehero_cli import refdocs
from beamtimehero_cli.cli.__main__ import (
    ToolParser,
    build_catalog_subtrees,
    build_ref_subtree,
    categorize,
    run_ref,
    run_tool_leaf,
    run_with,
)
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS

from beamline_tools.agent_roles import AGENT_ROLES

ROLE = "bth"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_DIR = PROJECT_ROOT / "context"

_BTH_REFDOCS: list[tuple[str, str, str]] = [
    ("spec-commands", "context/BL15-2_SPEC_Reference.txt",
     "BL15-2 SPEC beamline control command reference."),
    ("user-operations", "context/BL15-2_user_reference.txt",
     "BL15-2 user operations quick reference."),
    ("cryostat-procedures", "context/cryostat_procedures.txt",
     "Liquid helium cryostat operating procedures and safety rules."),
]


_refdocs_registered = False


def register_refdocs() -> None:
    """Idempotent: register BTH's local context docs with upstream's refdoc
    registry. Safe to call from app startup as well as the CLI builder."""
    global _refdocs_registered
    if _refdocs_registered:
        return
    for name, rel_path, description in _BTH_REFDOCS:
        refdocs.register_doc(name, PROJECT_ROOT / rel_path, description)
    _refdocs_registered = True


_BTH_ALLOWED_CATEGORIES = frozenset({"tool", "spec-read"})


def _filter_for_role(spec_write_allow: frozenset[str]) -> list[dict]:
    """Keep only `tool` / `spec-read` tools, plus any spec-write tools on
    the role's allowlist (empty for BTH). `db` tools are dropped."""
    filtered: list[dict] = []
    for tdef in TOOL_DEFINITIONS:
        fn = tdef.get("function") or {}
        name = fn.get("name")
        category = categorize(tdef)
        if category == "spec-write":
            if name in spec_write_allow:
                filtered.append(tdef)
            continue
        if category in _BTH_ALLOWED_CATEGORIES:
            filtered.append(tdef)
    return filtered


def bth_tool_definitions() -> list[dict]:
    """Public: the upstream tool defs that survive the bth filter."""
    return _filter_for_role(AGENT_ROLES[ROLE]["spec_write_tools"])


def _strip_empty_subtrees(branch_subs: argparse._SubParsersAction) -> None:
    """Drop `db` / `spec-write` subtrees if filtering left them with no leaves
    — otherwise --help would advertise commands the agent cannot invoke."""
    for tree_name in ("db", "spec-write"):
        tree_parser = branch_subs.choices.get(tree_name)
        if tree_parser is None:
            continue
        has_leaves = any(
            isinstance(a, argparse._SubParsersAction) and a.choices
            for a in tree_parser._actions
        )
        if has_leaves:
            continue
        del branch_subs.choices[tree_name]
        branch_subs._choices_actions = [
            a for a in branch_subs._choices_actions
            if getattr(a, "dest", None) != tree_name
        ]


def _build_bth_branch(trees: argparse._SubParsersAction) -> None:
    branch = trees.add_parser(
        ROLE,
        help="BeamtimeHero agent surface (ref, tool, spec-read).",
    )
    branch_subs = branch.add_subparsers(dest="subtree", metavar="<tree>")
    build_ref_subtree(branch_subs)
    build_catalog_subtrees(branch_subs, bth_tool_definitions())
    _strip_empty_subtrees(branch_subs)


def build_parser() -> argparse.ArgumentParser:
    register_refdocs()
    parser = ToolParser(
        prog="beamtimehero",
        description=(
            "BTH-scoped beamtimehero CLI. The `bth` branch holds every "
            "command the BeamtimeHero agent is allowed to run."
        ),
    )
    trees = parser.add_subparsers(dest="tree", metavar="<tree>")
    _build_bth_branch(trees)
    return parser


def dispatch(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    if getattr(args, "tree", None) != ROLE:
        parser.print_help()
        return 0
    subtree = getattr(args, "subtree", None)
    if not subtree:
        parser.parse_args([ROLE, "--help"])
        return 0
    if subtree == "ref":
        return run_ref(args)
    if not getattr(args, "leaf", None):
        parser.parse_args([ROLE, subtree, "--help"])
        return 0
    return run_tool_leaf(args)


_KNOWN_TREES = frozenset({ROLE})


def main(argv: list[str] | None = None) -> int:
    return run_with(build_parser, dispatch, argv, known_trees=_KNOWN_TREES)


# ---------------------------------------------------------------------------
# In-process entry point used by the server tool loop.
# ---------------------------------------------------------------------------

_PLOT_LINE_RE = re.compile(r'"(plot_path|image_paths)"')


def _split_argv(command_str: str) -> list[str]:
    """Strip the `beamtimehero` prefix (if any) and shlex-split."""
    cmd = command_str.strip()
    if cmd.startswith("beamtimehero"):
        cmd = cmd[len("beamtimehero"):].strip()
    return shlex.split(cmd) if cmd else []


def run_cli(command_str: str) -> tuple[str, list[str]]:
    """Run a `beamtimehero ...` command in-process.

    Returns (stdout_text, image_b64s). Plots written by the upstream tool
    runner land in `BEAMTIMEHERO_PLOTS_DIR` (or `./data/tool_plots/`);
    when the command's JSON output references `plot_path` / `image_paths`,
    those files are read and base64-encoded for the LLM/UI.
    """
    argv = _split_argv(command_str)
    buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = buf
    try:
        try:
            rc = main(argv)
        except SystemExit as e:
            rc = int(e.code or 0)
    finally:
        sys.stdout = real_stdout

    text = buf.getvalue()
    images_b64: list[str] = []
    if _PLOT_LINE_RE.search(text):
        images_b64 = _extract_images(text)
    return text, images_b64


def _extract_images(text: str) -> list[str]:
    """Pull `plot_path` / `image_paths` out of the CLI's JSON envelope and
    return their bytes base64-encoded."""
    import base64

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    paths: list[str] = []
    p = payload.get("plot_path")
    if isinstance(p, str):
        paths.append(p)
    extra = payload.get("image_paths") or []
    if isinstance(extra, list):
        for pth in extra:
            if isinstance(pth, str) and pth not in paths:
                paths.append(pth)
    out: list[str] = []
    for pth in paths:
        try:
            out.append(base64.b64encode(Path(pth).read_bytes()).decode("ascii"))
        except OSError:
            continue
    return out


if __name__ == "__main__":
    sys.exit(main())
