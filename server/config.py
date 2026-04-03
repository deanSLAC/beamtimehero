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
STANFORD_MODEL = os.getenv("STANFORD_MODEL", "claude-4-5-sonnet")

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# App
BASE_PATH = os.getenv("BASE_PATH", "/beamtimehero")

# Tools mode: "mcp" (full tool schemas) or "cli" (progressive discovery)
TOOLS_MODE = os.getenv("TOOLS_MODE", "cli")
