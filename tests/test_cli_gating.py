"""Layer-1 tool gating: the agent-facing binary must not even parse
spec-write/db/etc. unless BEAMTIMEHERO_FULL_CLI=1 is set."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "beamtimehero"

# Every canonical tree the gate must hide (mirrors _CATALOG_TREES in
# beamline_tools/cli.py).
CANONICAL_TREES = [
    "tool", "db", "spec-read", "spec-write", "spec-file", "s3df", "slack",
]


def _run(args, full_cli=False):
    env = os.environ.copy()
    env.pop("BEAMTIMEHERO_FULL_CLI", None)
    if full_cli:
        env["BEAMTIMEHERO_FULL_CLI"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )


@pytest.mark.parametrize("tree", CANONICAL_TREES)
def test_canonical_tree_rejected_by_default(tree):
    r = _run([tree, "--help"])
    assert r.returncode != 0
    assert "invalid choice" in r.stdout + r.stderr


def test_other_profiles_pruned_by_default():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "bl-aligner" not in r.stdout

    # Discovery must not advertise profiles the parser won't accept.
    r = _run(["--list-profiles"])
    assert r.returncode == 0
    assert "bl-aligner" not in r.stdout
    assert "bth" in r.stdout


def test_bth_and_ref_available_by_default():
    r = _run(["bth", "--help"])
    assert r.returncode == 0
    assert "list-scans" in r.stdout

    r = _run(["ref", "--list"])
    assert r.returncode == 0
    assert "cryostat-procedures" in r.stdout


def test_full_cli_env_flag_restores_catalog():
    r = _run(["spec-write", "--help"], full_cli=True)
    assert r.returncode == 0
    assert "usage: beamtimehero spec-write" in r.stdout


def test_build_parser_leaves_upstream_registry_intact(monkeypatch):
    """Pruning to bth must not permanently truncate upstream's global
    PROFILES registry for other in-process consumers."""
    monkeypatch.delenv("BEAMTIMEHERO_FULL_CLI", raising=False)
    from beamline_tools.cli import build_parser
    from beamtimehero_cli.cli.profiles import PROFILES

    before = dict(PROFILES)
    build_parser()
    assert dict(PROFILES) == {**before, "bth": PROFILES["bth"]}
