"""Data-directory configuration state.

An unconfigured scan or log directory must surface as "not configured" — the
tools that read it say so, rather than returning an empty result that reads
like "no scans exist". These tests pin that and the /api/status endpoint the
frontend reads.

Upstream used to offer a packaged sample-data fallback that BTH switched off
with BEAMTIMEHERO_NO_SAMPLE_FALLBACK. That fallback is gone: beamtimehero_cli
9acbef6 deleted the sample_data package and made USING_SAMPLE_DATA /
USING_SAMPLE_LOGS permanent False, so the env var no longer does anything and
setting it here would only make these tests look like they cover a branch that
does not exist. `test_upstream_has_no_sample_data_fallback` is the tripwire: if
it fails, upstream reintroduced a fallback and BTH has to decide again.
"""
import importlib
import pathlib


def _reload_cli_config():
    import beamtimehero_cli.config as c
    return importlib.reload(c)


def test_missing_dir_is_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("BL_LOGS_DIR", str(tmp_path / "missing-logs"))
    c = _reload_cli_config()
    try:
        assert c.SCAN_DIR_CONFIGURED is False
        assert c.LOGS_DIR_CONFIGURED is False
        # The intended path is kept, not rewritten to something that exists —
        # an operator reading the status page needs to see what they set.
        assert c.BL_SCAN_DIR == tmp_path / "missing"
        assert c.BL_LOGS_DIR == tmp_path / "missing-logs"
    finally:
        _reload_cli_config()  # restore process-wide module state


def test_dated_subdir_is_configured(monkeypatch, tmp_path):
    dated = tmp_path / "2026-06_beamtime"
    dated.mkdir()
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path))
    c = _reload_cli_config()
    try:
        assert c.SCAN_DIR_CONFIGURED is True
        assert c.BL_SCAN_DIR == dated
    finally:
        _reload_cli_config()


def test_upstream_has_no_sample_data_fallback(monkeypatch, tmp_path):
    """A missing directory must never resolve to packaged demo data.

    Serving demo scans from the beamline computer as though they were live is
    the specific failure BTH disabled the old fallback to avoid. Asserting the
    flags alone would be vacuous now that they are constants, so this also
    pins that the path is not redirected anywhere.
    """
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("BL_LOGS_DIR", str(tmp_path / "missing-logs"))
    c = _reload_cli_config()
    try:
        assert c.USING_SAMPLE_DATA is False
        assert c.USING_SAMPLE_LOGS is False
        # The real guarantee: neither path was redirected into the installed
        # package, which is where bundled demo data would have to live. A
        # substring check for "sample" cannot say this — pytest builds
        # tmp_path from the test's own name.
        package_root = pathlib.Path(c.__file__).resolve().parent
        assert package_root not in pathlib.Path(c.BL_SCAN_DIR).resolve().parents
        assert package_root not in pathlib.Path(c.BL_LOGS_DIR).resolve().parents
        assert pathlib.Path(c.BL_SCAN_DIR).resolve() == (tmp_path / "missing").resolve()
    finally:
        _reload_cli_config()


def test_api_status_reports_unconfigured(monkeypatch, tmp_path):
    # Call the route coroutine directly — avoids starting the app lifespan
    # (Slack bridge / claude health check) and the httpx test-client dep.
    import asyncio

    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    _reload_cli_config()
    try:
        import app as app_mod

        body = asyncio.run(app_mod.status())
        assert body["data_configured"] is False
        assert body["scan_dir"].endswith("missing")
    finally:
        _reload_cli_config()
