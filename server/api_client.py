"""Stanford AI API Gateway Client.

OpenAI-compatible wrapper for Stanford's AI API Gateway.
"""

import logging
from datetime import datetime
from pathlib import Path

import requests

from config import API_BASE_URL, API_KEY, STANFORD_MODEL, CONTEXT_DIR, TOOLS_MODE
from tools.cli import ALWAYS_IN_PROMPT

logger = logging.getLogger(__name__)


class StanfordAPIClient:
    """Client for Stanford AI API Gateway (OpenAI-compatible)."""

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or API_KEY
        self.model = model or STANFORD_MODEL

        if not self.api_key:
            raise ValueError(
                "API key required. Set API_KEY environment variable "
                "or pass api_key to constructor."
            )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _load_context_files(self) -> str:
        """Load .txt files from the context directory.

        In CLI tools mode, large reference docs are excluded from the system
        prompt (served on-demand via 'beamtimehero reference' instead).
        In MCP mode, all context files are included.
        """
        context_parts = []

        if CONTEXT_DIR.exists():
            for txt_file in sorted(CONTEXT_DIR.glob("*.txt")):
                if txt_file.name == "system_prompt.txt":
                    continue
                # In CLI mode, skip files that aren't in the always-include set
                if TOOLS_MODE == "cli" and txt_file.name not in ALWAYS_IN_PROMPT:
                    continue
                try:
                    content = txt_file.read_text().strip()
                    if content:
                        context_parts.append(
                            f"--- {txt_file.name} ---\n{content}"
                        )
                except Exception as e:
                    logger.warning("Could not read context file %s: %s", txt_file, e)

        return "\n\n".join(context_parts)

    def build_system_message(self) -> str:
        """Build system message with beamline context."""
        now = datetime.now()

        prompt_file = CONTEXT_DIR / "system_prompt.txt"
        try:
            base_prompt = prompt_file.read_text().strip()
        except Exception:
            base_prompt = "You are a helpful assistant for X-ray beamline operations."

        base_prompt += (
            f"\n\nCurrent date and time: "
            f"{now.strftime('%A, %B %d, %Y at %H:%M:%S')} (Pacific Time)."
        )

        context = self._load_context_files()
        if context:
            return f"{base_prompt}\n\nRelevant beamline context:\n{context}"

        return base_prompt

    def chat_completion(
        self,
        messages: list,
        include_context: bool = True,
        tools: list | None = None,
    ) -> dict:
        """Send a chat completion request."""
        url = f"{API_BASE_URL}/chat/completions"

        if include_context:
            system_msg = {"role": "system", "content": self.build_system_message()}
            messages = [system_msg] + messages

        payload = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        response = requests.post(
            url, headers=self._get_headers(), json=payload, timeout=120
        )
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        """Check if API is reachable and key is valid."""
        try:
            url = f"{API_BASE_URL}/models"
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return False
