"""The plots dir is per-session and accumulates; the scrape must only
pick up files written during the current turn."""
import os
import time

from claude_cli_backend import _scrape_session_plots_dir


def test_only_files_after_watermark(tmp_path):
    old = tmp_path / "turn1_plot.png"
    old.write_bytes(b"old")
    past = time.time() - 3600
    os.utime(old, (past, past))

    cutoff = time.time() - 10

    new = tmp_path / "turn2_plot.png"
    new.write_bytes(b"new")

    result = _scrape_session_plots_dir(tmp_path, since=cutoff)
    assert result == [str(new)]


def test_missing_dir_is_empty(tmp_path):
    assert _scrape_session_plots_dir(tmp_path / "nope", since=0.0) == []
