"""Slack bridge for BeamtimeHero.

Two-channel architecture:
- LLM channel: mirrors user questions and LLM responses (read-only for staff)
- Users channel: bidirectional staff-user communication
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import (
    SLACK_BOT_TOKEN,
    SLACK_APP_TOKEN,
    SLACK_LLM_CHANNEL_ID,
    SLACK_USERS_CHANNEL_ID,
)

logger = logging.getLogger(__name__)


class SlackBridge:
    """Bidirectional bridge between BeamtimeHero web app and Slack."""

    def __init__(self):
        self._llm_thread_ts: str | None = None
        self._staff_thread_ts: str | None = None
        self._on_staff_message: Callable[[str, str], None] | None = None
        self._app: App | None = None
        self._handler: SocketModeHandler | None = None
        self._bot_user_id: str | None = None

    def set_staff_callback(self, callback: Callable[[str, str], None]):
        """Set callback for when staff sends a message.

        callback(text, user_name)
        """
        self._on_staff_message = callback

    def start(self):
        """Start Slack bot in a background thread."""
        if not SLACK_BOT_TOKEN or not SLACK_APP_TOKEN:
            logger.warning("Slack tokens not configured — Slack bridge disabled")
            return

        self._app = App(token=SLACK_BOT_TOKEN)
        self._register_handlers()

        # Get our own bot user ID so we can ignore our own messages
        try:
            auth = self._app.client.auth_test()
            self._bot_user_id = auth["user_id"]
        except Exception as e:
            logger.warning("Could not get bot user ID: %s", e)

        self._handler = SocketModeHandler(self._app, SLACK_APP_TOKEN)

        thread = threading.Thread(target=self._handler.start, daemon=True)
        thread.start()
        logger.info(
            "Slack bridge started (LLM channel: %s, Staff channel: %s)",
            SLACK_LLM_CHANNEL_ID,
            SLACK_USERS_CHANNEL_ID,
        )

    def _register_handlers(self):
        @self._app.event("message")
        def handle_message(event, client):
            # Ignore bot messages (including our own)
            if event.get("bot_id") or event.get("subtype"):
                return

            channel = event.get("channel", "")

            # Only relay messages from the users channel
            if channel != SLACK_USERS_CHANNEL_ID:
                return

            # Only listen in our thread (if one exists)
            thread_ts = event.get("thread_ts")
            if self._staff_thread_ts and thread_ts != self._staff_thread_ts:
                return

            text = event.get("text", "").strip()
            if not text:
                return

            # Get staff member name
            user_id = event.get("user", "")
            staff_name = "Staff"
            if user_id:
                try:
                    info = client.users_info(user=user_id)
                    profile = info["user"].get("profile", {})
                    staff_name = (
                        profile.get("display_name")
                        or profile.get("real_name")
                        or user_id
                    )
                except Exception:
                    staff_name = user_id

            logger.info("Staff message from %s: %s", staff_name, text[:100])

            if self._on_staff_message:
                self._on_staff_message(text, staff_name)

    # --- LLM channel (read-only mirror) ---

    def post_user_message(self, user_text: str):
        """Forward a user question to the LLM Slack channel."""
        if not self._app or not SLACK_LLM_CHANNEL_ID:
            return

        try:
            if not self._llm_thread_ts:
                result = self._app.client.chat_postMessage(
                    channel=SLACK_LLM_CHANNEL_ID,
                    text=f"*New BeamtimeHero question:*\n> {user_text}",
                )
                self._llm_thread_ts = result["ts"]
            else:
                self._app.client.chat_postMessage(
                    channel=SLACK_LLM_CHANNEL_ID,
                    text=f"*User:*\n> {user_text}",
                    thread_ts=self._llm_thread_ts,
                )
        except Exception as e:
            logger.error("Failed to post user message to Slack: %s", e)

    def post_llm_response(self, llm_text: str):
        """Forward an LLM response to the LLM Slack thread."""
        if not self._app or not SLACK_LLM_CHANNEL_ID or not self._llm_thread_ts:
            return

        try:
            display_text = llm_text
            if len(display_text) > 3000:
                display_text = display_text[:3000] + "\n\n_(truncated)_"

            self._app.client.chat_postMessage(
                channel=SLACK_LLM_CHANNEL_ID,
                text=f"*AI Assistant:*\n{display_text}",
                thread_ts=self._llm_thread_ts,
            )
        except Exception as e:
            logger.error("Failed to post LLM response to Slack: %s", e)

    # --- Users channel (bidirectional staff-user chat) ---

    def post_user_to_staff(self, user_text: str):
        """Forward a user message to the users Slack channel."""
        if not self._app or not SLACK_USERS_CHANNEL_ID:
            return

        try:
            if not self._staff_thread_ts:
                result = self._app.client.chat_postMessage(
                    channel=SLACK_USERS_CHANNEL_ID,
                    text=f"*Beamline user:*\n> {user_text}",
                )
                self._staff_thread_ts = result["ts"]
            else:
                self._app.client.chat_postMessage(
                    channel=SLACK_USERS_CHANNEL_ID,
                    text=f"*Beamline user:*\n> {user_text}",
                    thread_ts=self._staff_thread_ts,
                )
        except Exception as e:
            logger.error("Failed to post user message to users channel: %s", e)

    def reset_thread(self):
        """Start new Slack threads for the next conversation."""
        self._llm_thread_ts = None
        self._staff_thread_ts = None
