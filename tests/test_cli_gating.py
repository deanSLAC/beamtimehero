"""Layer-1 tool gating: the agent-facing binary must not even parse
spec-write/db/etc. unless BEAMTIMEHERO_FULL_CLI=1 is set."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "beamtimehero"


def _run(args, full_cli=False):
    env = os.environ.copy()
    env.pop("BEAMTIMEHERO_FULL_CLI", None)
    if full_cli:
        env["BEAMTIMEHERO_FULL_CLI"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )


def test_spec_write_rejected_by_default():
    r = _run(["spec-write", "--help"])
    assert r.returncode != 0
    assert "invalid choice" in r.stdout + r.stderr


def test_db_rejected_by_default():
    r = _run(["db", "--help"])
    assert r.returncode != 0


def test_other_profiles_pruned_by_default():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "bl-aligner" not in r.stdout


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
    assert "justification" in r.stdout or "<command>" in r.stdout
