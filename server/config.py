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
CONTEXT_DIR = PROJECT_ROOT / "context"
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
    """Resolved at runtime from env vars with the gateway's prefix."""

    __slots__ = ("url", "key", "env")

    def __init__(self, prefix: str) -> None:
        self.url: str | None = os.environ.get(f"{prefix}BASE_URL") or None
        self.key: str = os.environ.get(f"{prefix}API_KEY") or ""
        env_block: dict[str, str] = {}
        skip = {"BASE_URL", "API_KEY"}
        for k, v in os.environ.items():
            if k.startswith(prefix) and k.removeprefix(prefix) not in skip:
                env_block[k.removeprefix(prefix)] = v
        self.env = env_block

    def as_dict(self) -> dict:
        return {"url": self.url, "key": self.key, "env": dict(self.env)}


_DEFAULT_GATEWAY = {"url": None, "key": "", "env": {}}

_GATEWAYS: dict[str, dict] = {
    "default": _DEFAULT_GATEWAY,
    "slac": _GatewayBlock("SLAC_").as_dict(),
    "stanford": _GatewayBlock("STANFORD_").as_dict(),
}


def gateway_config() -> dict:
    """Return {url, key, env} for the active LLM_GATEWAY."""
    return _GATEWAYS.get(LLM_GATEWAY, _DEFAULT_GATEWAY)


def llm_configured() -> bool:
    """True iff a usable gateway key is present for the active gateway."""
    return bool(gateway_config()["key"])
