"""Data-directory configuration state.

BTH disables upstream's sample-data fallback (BEAMTIMEHERO_NO_SAMPLE_FALLBACK)
so an unconfigured scan directory surfaces as "not configured" instead of
silently serving packaged demo data. These tests pin both branches and the
/api/status endpoint the frontend reads.
"""
import importlib

import pytest


def _reload_cli_config():
    import beamtimehero_cli.config as c
    return importlib.reload(c)


def test_no_fallback_marks_missing_dir_unconfigured(monkeypatch, tmp_path):
    monkeypatch.setenv("BEAMTIMEHERO_NO_SAMPLE_FALLBACK", "1")
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    monkeypatch.setenv("BL_LOGS_DIR", str(tmp_path / "missing-logs"))
    c = _reload_cli_config()
    try:
        assert c.SCAN_DIR_CONFIGURED is False
        assert c.USING_SAMPLE_DATA is False          # not demo data
        assert c.BL_SCAN_DIR == tmp_path / "missing"  # intended path kept
        assert c.LOGS_DIR_CONFIGURED is False
        assert c.USING_SAMPLE_LOGS is False
    finally:
        _reload_cli_config()  # restore process-wide module state


def test_dated_subdir_is_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("BEAMTIMEHERO_NO_SAMPLE_FALLBACK", "1")
    dated = tmp_path / "2026-06_beamtime"
    dated.mkdir()
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path))
    c = _reload_cli_config()
    try:
        assert c.SCAN_DIR_CONFIGURED is True
        assert c.BL_SCAN_DIR == dated
    finally:
        _reload_cli_config()


def test_fallback_default_still_serves_sample(monkeypatch, tmp_path):
    # With the flag off (upstream default), a missing dir falls back to the
    # packaged sample data — unchanged off-beamline CLI behavior.
    monkeypatch.delenv("BEAMTIMEHERO_NO_SAMPLE_FALLBACK", raising=False)
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    c = _reload_cli_config()
    try:
        assert c.USING_SAMPLE_DATA is True
        assert c.SCAN_DIR_CONFIGURED is False
    finally:
        _reload_cli_config()


def test_api_status_reports_unconfigured(monkeypatch, tmp_path):
    # Call the route coroutine directly — avoids starting the app lifespan
    # (Slack bridge / claude health check) and the httpx test-client dep.
    import asyncio

    monkeypatch.setenv("BEAMTIMEHERO_NO_SAMPLE_FALLBACK", "1")
    monkeypatch.setenv("BL_SCAN_DIR", str(tmp_path / "missing"))
    _reload_cli_config()
    try:
        import app as app_mod

        body = asyncio.run(app_mod.status())
        assert body["data_configured"] is False
        assert body["scan_dir"].endswith("missing")
    finally:
        _reload_cli_config()
