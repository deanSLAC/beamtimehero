"""mlflow_logging.run must never replace an exception raised in its body
("generator didn't stop after throw()") — the original error must reach
the user."""
import sys
import types

import pytest

import mlflow_logging


def test_disabled_path_propagates_body_exception():
    with pytest.raises(ValueError, match="real error"):
        with mlflow_logging.run(experiment="x"):
            raise ValueError("real error")


def test_enabled_path_propagates_body_exception(monkeypatch):
    fake_mlflow = types.ModuleType("mlflow")
    fake_mlflow.start_run = lambda **kw: object()
    fake_mlflow.end_run = lambda: None
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(mlflow_logging, "_enabled", lambda: True)
    monkeypatch.setattr(
        mlflow_logging, "get_or_create_experiment", lambda name: "exp1"
    )

    with pytest.raises(RuntimeError, match="claude exited"):
        with mlflow_logging.run(experiment="x") as r:
            assert r is not None
            raise RuntimeError("claude exited with code 1")


def test_enabled_path_end_run_called(monkeypatch):
    calls = []
    fake_mlflow = types.ModuleType("mlflow")
    fake_mlflow.start_run = lambda **kw: object()
    fake_mlflow.end_run = lambda: calls.append("end")
    monkeypatch.setitem(sys.modules, "mlflow", fake_mlflow)
    monkeypatch.setattr(mlflow_logging, "_enabled", lambda: True)
    monkeypatch.setattr(
        mlflow_logging, "get_or_create_experiment", lambda name: "exp1"
    )

    with mlflow_logging.run(experiment="x"):
        pass
    assert calls == ["end"]

    calls.clear()
    with pytest.raises(ValueError):
        with mlflow_logging.run(experiment="x"):
            raise ValueError("boom")
    assert calls == ["end"], "end_run must also run on the exception path"


def test_setup_failure_yields_none_and_swallows(monkeypatch):
    monkeypatch.setattr(mlflow_logging, "_enabled", lambda: True)
    monkeypatch.setattr(
        mlflow_logging, "get_or_create_experiment",
        lambda name: (_ for _ in ()).throw(ConnectionError("server down")),
    )
    with mlflow_logging.run(experiment="x") as r:
        assert r is None  # setup failures stay best-effort
