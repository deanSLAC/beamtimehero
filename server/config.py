"""Shared configuration for BeamtimeHero.

LLM access goes through Claude Code (`claude -p`), which we point at a
LiteLLM gateway by exporting `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`,
and a per-gateway env block into the subprocess. `gateway_config()`
returns the resolved block for the currently selected `LLM_GATEWAY`.
Pattern lifted from `../autonomous/orchestration/config.py`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
STATIC_DIR = PROJECT_ROOT / "static"

# LLM gateway selection
LLM_GATEWAY = os.getenv("LLM_GATEWAY", "default")
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_LLM_CHANNEL_ID = os.getenv("SLACK_LLM_CHANNEL_ID", "")
SLACK_USERS_CHANNEL_ID = os.getenv("SLACK_USERS_CHANNEL_ID", "")

# App
BASE_PATH = os.getenv("BASE_PATH", "")

# MLflow tracing
MLFLOW_ENABLED = os.getenv("MLFLOW_ENABLED", "0") == "1"
MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "https://isaac.slac.stanford.edu/mlflow/api/external",
)
MLFLOW_TOKEN = os.getenv("MLFLOW_TRACKING_TOKEN", "")


# ---------------------------------------------------------------------------
# Gateway resolution
# ---------------------------------------------------------------------------
class _GatewayBlock:
    """Resolved at runtime from env vars with the gateway's prefix.

    `<P>API_KEY_PRIMARY` (optional) is tried first; `<P>API_KEY` is the
    fallback while the primary cools down from a rate limit. With only
    `<P>API_KEY` set this is the single-key behaviour it always was.
    `<P>MODEL_ALIAS` (optional) becomes `ANTHROPIC_MODEL`.
    """

    __slots__ = ("url", "keys", "model_alias", "env")

    def __init__(self, prefix: str) -> None:
        self.url: str | None = os.environ.get(f"{prefix}BASE_URL") or None
        self.keys: list[tuple[str, str]] = [
            (name, os.environ[f"{prefix}{name}"])
            for name in ("API_KEY_PRIMARY", "API_KEY")
            if os.environ.get(f"{prefix}{name}")
        ]
        self.model_alias: str | None = os.environ.get(f"{prefix}MODEL_ALIAS") or None
        env_block: dict[str, str] = {}
        skip = {"BASE_URL", "API_KEY", "API_KEY_PRIMARY", "MODEL_ALIAS"}
        for k, v in os.environ.items():
            if k.startswith(prefix) and k.removeprefix(prefix) not in skip:
                env_block[k.removeprefix(prefix)] = v
        self.env = env_block

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "key": self.keys[0][1] if self.keys else "",
            "keys": list(self.keys),
            "model_alias": self.model_alias,
            "env": dict(self.env),
        }


_DEFAULT_GATEWAY = {"url": None, "key": "", "keys": [], "model_alias": None, "env": {}}

_GATEWAYS: dict[str, dict] = {
    "default": _DEFAULT_GATEWAY,
    "slac": _GatewayBlock("SLAC_").as_dict(),
    "stanford": _GatewayBlock("STANFORD_").as_dict(),
}


def gateway_config() -> dict:
    """Return {url, key, keys, model_alias, env} for the active LLM_GATEWAY."""
    return _GATEWAYS.get(LLM_GATEWAY, _DEFAULT_GATEWAY)


# Rate-limit failover: a key that hit a rate limit sits out this long, and
# the next key in order (primary -> fallback) is used meanwhile. The key is
# baked into the subprocess env at spawn, so failover takes effect on the
# next turn, not mid-turn.
KEY_COOLDOWN_SECONDS = float(os.getenv("BEAMTIMEHERO_KEY_COOLDOWN_SECONDS", "900"))
_key_cooldown_until: dict[str, float] = {}


def active_gateway_key() -> tuple[str, str] | None:
    """(name, key) to use for the next spawn, or None if the gateway has no key."""
    import time

    keys = gateway_config()["keys"]
    now = time.time()
    for name, key in keys:
        if _key_cooldown_until.get(name, 0.0) <= now:
            return name, key
    return keys[-1] if keys else None


def note_gateway_rate_limited(key_name: str) -> None:
    """Cool down `key_name` so the next spawn uses the other key (if any)."""
    import time

    if len(gateway_config()["keys"]) > 1:
        _key_cooldown_until[key_name] = time.time() + KEY_COOLDOWN_SECONDS


def looks_rate_limited(text: str) -> bool:
    low = (text or "").lower()
    return "429" in low or "rate_limit" in low or "rate limit" in low


def llm_configured() -> bool:
    """True iff the active gateway is usable.

    The "default" gateway means a locally-authenticated `claude` binary,
    which needs no API key here — binary availability is covered by
    `ClaudeCLIClient.health_check()`. Named gateways require their key.
    """
    if LLM_GATEWAY == "default":
        return True
    return bool(gateway_config()["keys"])
