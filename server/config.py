"""Shared configuration for BeamtimeHero."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
CONTEXT_DIR = PROJECT_ROOT / "context"
STATIC_DIR = PROJECT_ROOT / "static"

# Stanford AI API Gateway
API_BASE_URL = "https://aiapi-prod.stanford.edu/v1"
API_KEY = os.getenv("API_KEY", "")
STANFORD_MODEL = os.getenv("STANFORD_MODEL", "claude-4-6-opus")

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_LLM_CHANNEL_ID = os.getenv("SLACK_LLM_CHANNEL_ID", "")
SLACK_USERS_CHANNEL_ID = os.getenv("SLACK_USERS_CHANNEL_ID", "")

# App
BASE_PATH = os.getenv("BASE_PATH", "")

# Tools mode: "mcp" (full tool schemas) or "cli" (progressive discovery)
TOOLS_MODE = os.getenv("TOOLS_MODE", "cli")

# MLflow tracing
MLFLOW_ENABLED = os.getenv("MLFLOW_ENABLED", "0") == "1"
MLFLOW_TRACKING_URI = os.getenv(
    "MLFLOW_TRACKING_URI",
    "https://isaac.slac.stanford.edu/mlflow/api/external",
)
MLFLOW_TOKEN = os.getenv("MLFLOW_TRACKING_TOKEN", "")
