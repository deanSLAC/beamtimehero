"""Slack bridge for BeamtimeHero.

Three integration modes:
- LLM channel: mirrors user-LLM conversation; staff replies go to the LLM
- Users channel: pure relay between web app users and staff in Slack
- Staff DMs: staff can DM the bot to start independent chat sessions
"""
from __future__ import annotations

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
        # callback(text, staff_name) for #users channel relay
        self._on_staff_message: Callable[[str, str], None] | None = None
        # callback(text, staff_name) for staff replies in #llm thread
        self._on_llm_thread_reply: Callable[[str, str], None] | None = None
        # callback(text, staff_name, dm_thread_key) for staff DMs
        self._on_dm_message: Callable[[str, str, str], None] | None = None
        self._app: App | None = None
        self._handler: SocketModeHandler | None = None
        self._bot_user_id: str | None = None

    def set_staff_callback(self, callback: Callable[[str, str], None]):
        """Set callback for staff messages in the #users channel (pure relay)."""
        self._on_staff_message = callback

    def set_llm_thread_callback(self, callback: Callable[[str, str], None]):
        """Set callback for staff replies in the #llm channel thread."""
        self._on_llm_thread_reply = callback

    def set_dm_callback(self, callback: Callable[[str, str, str], None]):
        """Set callback for staff DM messages."""
        self._on_dm_message = callback

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
            "Slack bridge started (LLM: %s, Users: %s)",
            SLACK_LLM_CHANNEL_ID,
            SLACK_USERS_CHANNEL_ID,
        )

    def _resolve_staff_name(self, user_id: str, client) -> str:
        """Look up a Slack user's display name."""
        if not user_id:
            return "Staff"
        try:
            info = client.users_info(user=user_id)
            profile = info["user"].get("profile", {})
            return (
                profile.get("display_name")
                or profile.get("real_name")
                or user_id
            )
        except Exception:
            return user_id

    def _register_handlers(self):
        @self._app.event("message")
        def handle_message(event, client):
            # Ignore bot messages (including our own)
            if event.get("bot_id") or event.get("subtype"):
                return

            channel = event.get("channel", "")
            channel_type = event.get("channel_type", "")
            thread_ts = event.get("thread_ts")
            text = event.get("text", "").strip()
            user_id = event.get("user", "")

            if not text:
                return

            # --- Staff DMs to the bot ---
            if channel_type == "im":
                staff_name = self._resolve_staff_name(user_id, client)
                msg_ts = event.get("ts", "")
                dm_thread_key = f"{channel}:{thread_ts or msg_ts}"
                logger.info("Staff DM from %s: %s", staff_name, text[:100])
                if self._on_dm_message:
                    self._on_dm_message(text, staff_name, dm_thread_key)
                return

            # --- Staff replies in #llm channel thread ---
            if channel == SLACK_LLM_CHANNEL_ID:
                # Only accept thread replies in our active thread
                if not thread_ts or thread_ts != self._llm_thread_ts:
                    return
                staff_name = self._resolve_staff_name(user_id, client)
                logger.info("LLM thread reply from %s: %s", staff_name, text[:100])
                if self._on_llm_thread_reply:
                    self._on_llm_thread_reply(text, staff_name)
                return

            # --- #users channel messages (pure relay) ---
            if channel != SLACK_USERS_CHANNEL_ID:
                return

            # Accept thread replies in our thread, or top-level messages
            if self._staff_thread_ts:
                if thread_ts and thread_ts != self._staff_thread_ts:
                    return

            staff_name = self._resolve_staff_name(user_id, client)
            logger.info("Staff message from %s: %s", staff_name, text[:100])

            if self._on_staff_message:
                self._on_staff_message(text, staff_name)

    # --- LLM channel (user-LLM mirror, staff can reply) ---

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

    # --- Users channel (pure relay, no LLM) ---

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

    # --- Staff DM replies ---

    def post_dm_reply(self, channel: str, thread_ts: str, text: str):
        """Post an LLM response back to a staff DM thread."""
        if not self._app:
            return

        try:
            display_text = text
            if len(display_text) > 3000:
                display_text = display_text[:3000] + "\n\n_(truncated)_"

            self._app.client.chat_postMessage(
                channel=channel,
                text=f"*AI Assistant:*\n{display_text}",
                thread_ts=thread_ts,
            )
        except Exception as e:
            logger.error("Failed to post DM reply: %s", e)

    def reset_thread(self):
        """Start new Slack threads for the next conversation."""
        self._llm_thread_ts = None
        self._staff_thread_ts = None
