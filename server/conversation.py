"""Conversation service for BeamtimeHero.

Owns one Claude Code session UUID and routes every user/staff turn through
`claude -p --resume`. The model's true memory lives in Claude Code's
session store on disk; `self.messages` is kept only as a display log for
`get_history()` (the frontend reads it to render the chat pane).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from claude_cli_backend import ClaudeCLIClient, send_and_collect

logger = logging.getLogger(__name__)


@dataclass
class ConversationResult:
    """Result of a single LLM interaction."""
    text: str
    images: list[str] = field(default_factory=list)


class ConversationService:
    """One conversation = one Claude Code session.

    The first turn uses `--session-id <uuid>` to mint the session; every
    turn after uses `--resume <uuid>`. To reset, build a new instance.
    """

    AGENT_NAME = "beamline-bth"

    def __init__(self, client: ClaudeCLIClient | None = None):
        self.client = client or ClaudeCLIClient()
        self.session_id: str = self.client.create_session()
        self.is_started: bool = False
        self.messages: list[dict] = []
        self._staff_buffer: list[str] = []

    def _flush_staff_context(self) -> str:
        """Drain buffered staff messages into a context string."""
        if not self._staff_buffer:
            return ""
        context = "\n".join(self._staff_buffer)
        self._staff_buffer.clear()
        return context

    def _record_assistant(self, result: ConversationResult) -> None:
        stored_text = result.text
        if result.images:
            stored_text += f"\n\n[{len(result.images)} plot(s) generated]"
        self.messages.append({"role": "assistant", "content": stored_text})

    def _run_turn(
        self,
        user_text: str,
        *,
        source: str,
        staff_name: str | None = None,
    ) -> ConversationResult:
        try:
            text, _tools, images = send_and_collect(
                self.client,
                self.session_id,
                user_text,
                source=source,
                is_new_session=not self.is_started,
                agent=self.AGENT_NAME,
                staff_name=staff_name,
            )
        except Exception as e:
            logger.error("Claude turn failed: %s", e, exc_info=True)
            return ConversationResult(text=f"Error: {e}")

        self.is_started = True
        return ConversationResult(text=text, images=images)

    def handle_message(
        self, user_text: str, source: str = "web"
    ) -> ConversationResult:
        """Process a user message through the LLM.

        Any buffered staff messages are prepended as context.
        """
        staff_context = self._flush_staff_context()
        if staff_context:
            combined = f"{staff_context}\n\n[Beamline user]: {user_text}"
        else:
            combined = user_text

        self.messages.append({"role": "user", "content": combined})

        result = self._run_turn(combined, source=source)
        self._record_assistant(result)
        return result

    def handle_staff_llm(
        self,
        staff_text: str,
        staff_name: str = "Staff",
        source: str = "slack_llm_thread",
    ) -> ConversationResult:
        """Route a staff !LLM message directly to the LLM."""
        content = f"[Staff member {staff_name}]: {staff_text}"
        self.messages.append({"role": "user", "content": content})

        result = self._run_turn(content, source=source, staff_name=staff_name)
        self._record_assistant(result)
        return result

    def buffer_staff_message(self, staff_text: str, staff_name: str = "Staff"):
        """Buffer a staff message for inclusion as context in the next user message."""
        self._staff_buffer.append(f"[Staff member {staff_name}]: {staff_text}")

    def get_history(self) -> list[dict]:
        """Return the conversation history (display log)."""
        return list(self.messages)
