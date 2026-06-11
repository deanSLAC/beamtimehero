"""Best-effort MLflow tracing helpers for BeamtimeHero.

The `run` context manager is the single entry point. It MUST NEVER raise:
MLflow logging must not break a user turn.

Two call sites share this helper:
- server/conversation.py            (chat tool loop, 3 entry points)
- server/app.py submit_suggestion   (suggestion classifier)
"""
from __future__ import annotations

import base64
import contextlib
import io
import logging
import os

# Bound MLflow HTTP timeouts BEFORE any mlflow symbol is imported.
# BTH talks to the tracking server over WAN/HTTPS, so an unreachable server
# would otherwise hang start_run() for 120s+ even with try/except.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "5")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "1")

from config import MLFLOW_ENABLED, MLFLOW_TOKEN  # noqa: E402

log = logging.getLogger(__name__)
_exp_cache: dict[str, str] = {}


def _enabled() -> bool:
    # Token absence disables silently rather than 401-ing every call.
    return MLFLOW_ENABLED and bool(MLFLOW_TOKEN)


def get_or_create_experiment(name: str) -> str | None:
    if not _enabled():
        return None
    if name in _exp_cache:
        return _exp_cache[name]
    import mlflow

    exp = mlflow.get_experiment_by_name(name)
    eid = exp.experiment_id if exp else mlflow.create_experiment(name)
    _exp_cache[name] = eid
    return eid


@contextlib.contextmanager
def run(experiment: str, run_name: str | None = None, **tags):
    """Best-effort MLflow Run context. Yields the active run, or None on failure/disabled.

    Only MLflow's own setup failures are swallowed. The `yield` to the
    caller sits OUTSIDE the except: an exception raised in the with-body
    (e.g. a failed claude turn) must propagate untouched — wrapping the
    yield in `except Exception` would make contextlib re-enter the
    generator and surface as "generator didn't stop after throw()",
    masking the real error.
    """
    if not _enabled():
        yield None
        return

    r = None
    mlflow = None
    try:
        import mlflow  # noqa: F811

        eid = get_or_create_experiment(experiment)
        str_tags = {k: str(v) for k, v in tags.items() if v is not None}
        r = mlflow.start_run(experiment_id=eid, run_name=run_name, tags=str_tags)
    except Exception:
        log.warning("MLflow logging failed", exc_info=True)
        yield None
        return

    try:
        yield r
    finally:
        try:
            mlflow.end_run()
        except Exception:
            log.warning("MLflow end_run failed", exc_info=True)


def decode_b64_png(b64: str):
    """Decode a base64-encoded PNG into a PIL.Image for mlflow.log_image()."""
    from PIL import Image

    return Image.open(io.BytesIO(base64.b64decode(b64)))
