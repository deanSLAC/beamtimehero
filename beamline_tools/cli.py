"""BTH `beamtimehero` CLI: upstream parser + the `bth` agent profile.

The wrapper composes upstream's CLI helpers and registers the BTH
profile (`beamline_tools.bth_profile`). The profile is a curated view
of the master catalog whose kebab leaves alias canonical
`(tree, ..., name)` paths. Discovery: `beamtimehero --list-profiles`,
`beamtimehero bth --help`.

Importable from the server (`run_cli(...)`) and invokable as a script
via `scripts/beamtimehero`. Errors → JSON `{"ok": false, "error": ...}`
on stdout, non-zero exit. Successful tool calls print the tool's stdout
(image paths included) and exit 0.
"""

from __future__ import annotations

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
    build_profile_subtrees,
    build_ref_subtree,
    dispatch as _cli_dispatch,
    run_with,
)
from beamtimehero_cli.cli.profiles import register_profile
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS

from beamline_tools.bth_profile import PROFILE as _BTH_PROFILE

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
    build_catalog_subtrees(trees, TOOL_DEFINITIONS)
    build_profile_subtrees(trees, TOOL_DEFINITIONS)
    return parser


_KNOWN_TREES = frozenset({
    "ref", "tool", "db", "spec-read", "spec-write",
    "spec-file", "s3df", "slack",
    _BTH_PROFILE["name"],
})


def main(argv: list[str] | None = None) -> int:
    return run_with(build_parser, _cli_dispatch, argv, known_trees=_KNOWN_TREES)


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
            main(argv)
        except SystemExit as e:
            int(e.code or 0)
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
