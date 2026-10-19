"""BL4-1 station surface: every alias resolves, only the note writers write, docs exist.

The station is chosen at import (BTH_STATION), so the check runs in a
subprocess with the variable set rather than reloading modules here.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Canonical tools that write files, the DB, Slack or SPEC, or that act on
# hardware despite reading (`ct`). None may reach the BL4-1 chat agent.
# write_summary and save_plan are allowed: notes into the user's dir.
FORBIDDEN = {
    "write_macro", "record_energy_calibration",
    "record_provenance", "export_results_bundle", "evaluate_spec_macro",
    "get_counts", "get_counter", "capture_sample_image",
    "cherfd_wait_for_scan",
}

_PROBE = r"""
import json
import beamline_tools.config  # noqa: F401
from beamline_tools.station import STATION
from beamtimehero_cli.tool_catalog import TOOL_DEFINITIONS
from beamtimehero_cli.tool_catalog.categorize import categorize
from beamtimehero_cli.tool_catalog.lineage import TOOL_LINEAGE

paths = {categorize(t) + (t["function"]["name"],) for t in TOOL_DEFINITIONS}
aliases = STATION.PROFILE["aliases"]
print(json.dumps({
    "station": STATION.NAME,
    "agent": STATION.AGENT,
    "settings": STATION.SETTINGS,
    "missing": [a for a, c in aliases.items() if tuple(c) not in paths],
    "trees": sorted({c[0] for c in aliases.values()}),
    "names": [c[-1] for c in aliases.values()],
    "mutating": [c[-1] for c in aliases.values()
                 if (TOOL_LINEAGE.get(c[-1]) or {}).get("mutates")],
    "refdocs": [p for _, p, _ in STATION.REFDOCS],
}))
"""


def _probe() -> dict:
    env = {**os.environ, "BTH_STATION": "bl41"}
    r = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True,
        env=env, cwd=str(ROOT), timeout=120,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_bl41_surface_is_read_only_and_resolves():
    s = _probe()
    assert s["station"] == "bl41"
    assert not s["missing"], f"bl41 aliases that no longer resolve: {s['missing']}"
    assert not s["mutating"], f"mutating tools in the bl41 profile: {s['mutating']}"
    assert not FORBIDDEN & set(s["names"]), FORBIDDEN & set(s["names"])
    assert set(s["trees"]) <= {"spec-file", "spec-read", "exafs", "tool", "db", "cherfd-read"}
    assert (ROOT / ".claude" / "agents" / f"{s['agent']}.md").is_file()
    assert (ROOT / s["settings"]).is_file()
    for rel in s["refdocs"]:
        assert (ROOT / rel).is_file(), rel


def test_unknown_station_refuses_to_start():
    env = {**os.environ, "BTH_STATION": "bl99"}
    r = subprocess.run(
        [sys.executable, "-c", "import beamline_tools.station"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=60,
    )
    assert r.returncode != 0 and "not a known station" in r.stderr
