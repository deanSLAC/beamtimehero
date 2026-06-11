"""Conversation service for BeamtimeHero.

Owns one Claude Code session UUID and routes every user/staff turn through
`claude -p --resume`. The model's true memory lives in Claude Code's
session store on disk; `self.messages` is a display log served to the
frontend via GET /api/history and persisted (text only) to
`data/conversation_state.json` so a server restart resumes the same
session and the UI can replay the transcript.

Turns are serialized: a `threading.Lock` is held for the whole turn, so a
staff reply arriving from the Slack thread while a web turn is in flight
queues behind it instead of spawning a concurrent `claude --resume`
against the same session.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from claude_cli_backend import ClaudeCLIClient, send_and_collect

logger = logging.getLogger(__name__)

STATE_FILE = Path(
    os.getenv("BEAMTIMEHERO_DATA_DIR", str(Path(__file__).parent.parent / "data"))
) / "conversation_state.json"


@dataclass
class ConversationResult:
    """Result of a single LLM interaction."""
    text: str
    images: list[str] = field(default_factory=list)
    message_id: str = ""


def new_message_id() -> str:
    return uuid.uuid4().hex


class ConversationService:
    """One conversation = one Claude Code session.

    The first turn uses `--session-id <uuid>` to mint the session; every
    turn after uses `--resume <uuid>`. To reset, build a new instance.
    """

    AGENT_NAME = "beamline-bth"

    def __init__(
        self,
        client: ClaudeCLIClient | None = None,
        on_tool_status: Optional[Callable[[list[str]], None]] = None,
        persist: bool = True,
    ):
        self.client = client or ClaudeCLIClient()
        self.session_id: str = self.client.create_session()
        self.is_started: bool = False
        self.messages: list[dict] = []
        self.on_tool_status = on_tool_status
        self._persist = persist
        self._turn_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def from_state(
        cls,
        client: ClaudeCLIClient | None = None,
        on_tool_status: Optional[Callable[[list[str]], None]] = None,
    ) -> "ConversationService | None":
        """Rebuild a service from the persisted manifest, or None."""
        try:
            state = json.loads(STATE_FILE.read_text())
            session_id = state["session_id"]
            is_started = bool(state["is_started"])
            messages = state.get("messages", [])
        except FileNotFoundError:
            return None
        except Exception:
            logger.warning("Unreadable conversation manifest %s", STATE_FILE,
                           exc_info=True)
            return None

        svc = cls(client=client, on_tool_status=on_tool_status)
        svc.session_id = session_id
        svc.is_started = is_started
        svc.messages = [m for m in messages if isinstance(m, dict)]
        logger.info(
            "Restored conversation from manifest (session=%s, %d messages)",
            session_id, len(svc.messages),
        )
        return svc

    def _save_state(self) -> None:
        """Atomically persist {session_id, is_started, messages} — text only
        (image b64 stripped to keep the file small; plots stay on disk)."""
        if not self._persist:
            return
        try:
            slim = [
                {k: v for k, v in m.items() if k != "images"}
                | ({"plot_count": len(m["images"])} if m.get("images") else {})
                for m in self.messages
            ]
            payload = json.dumps({
                "session_id": self.session_id,
                "is_started": self.is_started,
                "messages": slim,
            })
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATE_FILE.with_suffix(".json.tmp")
            tmp.write_text(payload)
            tmp.replace(STATE_FILE)
        except Exception:
            logger.warning("Failed to persist conversation state", exc_info=True)

    @staticmethod
    def clear_state() -> None:
        """Drop the persisted manifest (called on reset)."""
        try:
            STATE_FILE.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove %s", STATE_FILE, exc_info=True)

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def _record(
        self,
        role: str,
        text: str,
        images: list[str] | None = None,
        mid: str | None = None,
    ) -> str:
        mid = mid or new_message_id()
        msg = {"id": mid, "role": role, "content": text}
        if images:
            msg["images"] = images
        self.messages.append(msg)
        return mid

    def _run_turn(
        self,
        user_text: str,
        *,
        source: str,
        staff_name: str | None = None,
    ) -> ConversationResult:
        was_started = self.is_started
        try:
            text, _tools, images = send_and_collect(
                self.client,
                self.session_id,
                user_text,
                source=source,
                is_new_session=not self.is_started,
                agent=self.AGENT_NAME,
                staff_name=staff_name,
                on_tool_start=self.on_tool_status,
            )
        except Exception as e:
            logger.error("Claude turn failed: %s", e, exc_info=True)
            if not was_started:
                # The failed first turn may have created the session on disk;
                # retrying --session-id with the same UUID would be rejected.
                # Mint a fresh one so the user's retry starts clean.
                self.session_id = self.client.create_session()
                logger.info("Re-minted session after first-turn failure: %s",
                            self.session_id)
                return ConversationResult(text=f"Error: {e}")
            # Resume failure (session store gone / corrupted / claude
            # upgraded): re-mint so the NEXT message starts a fresh session
            # instead of erroring forever. No silent retry.
            self.session_id = self.client.create_session()
            self.is_started = False
            self._save_state()
            logger.error(
                "Resume failed; re-minted session %s. Next message starts "
                "with fresh context.", self.session_id,
            )
            return ConversationResult(
                text=(
                    f"Error: {e}\n\n_The previous session could not be "
                    "resumed; your next message will start a fresh "
                    "conversation (the transcript above is display-only)._"
                )
            )

        self.is_started = True
        return ConversationResult(text=text, images=images)

    def _locked_turn(
        self,
        content: str,
        *,
        source: str,
        staff_name: str | None = None,
        message_id: str | None = None,
    ) -> ConversationResult:
        """Serialize: record the user message, run the turn, record the reply."""
        with self._turn_lock:
            self._record(
                "user" if staff_name is None else "staff", content, mid=message_id
            )
            result = self._run_turn(content, source=source, staff_name=staff_name)
            result.message_id = self._record(
                "assistant", result.text, result.images
            )
            self._save_state()
            return result

    def handle_message(
        self, user_text: str, source: str = "web", message_id: str | None = None
    ) -> ConversationResult:
        """Process a user message through the LLM.

        `message_id` lets the caller pre-announce the user message over the
        WebSocket with the same id the history will carry.
        """
        return self._locked_turn(user_text, source=source, message_id=message_id)

    def handle_staff_llm(
        self,
        staff_text: str,
        staff_name: str = "Staff",
        source: str = "slack_llm_thread",
        message_id: str | None = None,
    ) -> ConversationResult:
        """Route a staff message in the LLM thread directly to the LLM."""
        content = f"[Staff member {staff_name}]: {staff_text}"
        return self._locked_turn(
            content, source=source, staff_name=staff_name, message_id=message_id
        )

    def get_history(self) -> list[dict]:
        """Return the conversation history (display log, incl. images)."""
        return list(self.messages)
