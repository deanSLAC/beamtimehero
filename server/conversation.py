"""Conversation service for BeamtimeHero.

Manages message history and LLM interaction with tool-use support.
Supports two tool modes:
- MCP: Native function-calling with full tool schemas
- CLI: Single run_command tool with progressive discovery
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from api_client import StanfordAPIClient
from config import TOOLS_MODE
from tools import TOOL_DEFINITIONS, CLI_TOOL_DEFINITION
from tools.executor import execute_tool
from tools.cli import run_cli

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5


@dataclass
class ConversationResult:
    """Result of a single LLM interaction."""
    text: str
    images: list[str] = field(default_factory=list)


class ConversationService:
    """Manages a single conversation session with the LLM."""

    def __init__(self, api_client: StanfordAPIClient):
        self.client = api_client
        self.messages: list[dict] = []
        self._staff_buffer: list[str] = []

    def _flush_staff_context(self) -> str:
        """Drain buffered staff messages into a context string."""
        if not self._staff_buffer:
            return ""
        context = "\n".join(self._staff_buffer)
        self._staff_buffer.clear()
        return context

    def _get_tool_definitions(self) -> list[dict]:
        """Return tool definitions based on configured mode."""
        if TOOLS_MODE == "cli":
            return CLI_TOOL_DEFINITION
        return TOOL_DEFINITIONS

    def _execute_tool_call(
        self, tool_name: str, tool_args: dict
    ) -> tuple[str, list[str]]:
        """Execute a single tool call, routing by mode.

        Returns (result_text, images_b64).
        """
        if TOOLS_MODE == "cli" and tool_name == "run_command":
            return run_cli(tool_args.get("command", ""))
        return execute_tool(tool_name, tool_args)

    def _run_tool_loop(self, messages: list[dict]) -> ConversationResult:
        """Run the LLM request with a multi-round tool loop.

        Args:
            messages: Conversation messages (without system message).
        """
        tools = self._get_tool_definitions()
        all_images: list[str] = []

        result = self.client.chat_completion(messages, tools=tools)
        assistant_msg = result["choices"][0]["message"]
        tool_calls = assistant_msg.get("tool_calls")

        tool_round = 0
        # Build API message history for tool rounds (includes system msg from client)
        api_messages = messages.copy()

        while tool_calls and tool_round < MAX_TOOL_ROUNDS:
            tool_round += 1
            api_messages.append(assistant_msg)

            for tool_call in tool_calls:
                func = tool_call["function"]
                tool_name = func["name"]
                raw_args = func["arguments"]
                tool_args = (
                    json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                )

                logger.info("Tool call: %s(%s)", tool_name, tool_args)
                tool_result, images_b64 = self._execute_tool_call(tool_name, tool_args)
                all_images.extend(images_b64)

                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_result,
                })

            result = self.client.chat_completion(
                api_messages, include_context=False, tools=tools
            )
            assistant_msg = result["choices"][0]["message"]
            tool_calls = assistant_msg.get("tool_calls")

        response_text = assistant_msg.get("content", "")
        return ConversationResult(text=response_text, images=all_images)

    def handle_message(self, user_text: str) -> ConversationResult:
        """Process a user message through the LLM.

        Any buffered staff messages are prepended as context.
        """
        staff_context = self._flush_staff_context()
        if staff_context:
            combined = f"{staff_context}\n\n[Beamline user]: {user_text}"
        else:
            combined = user_text

        self.messages.append({"role": "user", "content": combined})

        try:
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
            ]
            result = self._run_tool_loop(api_messages)
        except Exception as e:
            logger.error("Chat response error: %s", e, exc_info=True)
            result = ConversationResult(text=f"Error: {e}")

        # Store text in history (omit images to keep context lean)
        stored_text = result.text
        if result.images:
            stored_text += f"\n\n[{len(result.images)} plot(s) generated]"
        self.messages.append({"role": "assistant", "content": stored_text})

        return result

    def handle_staff_llm(self, staff_text: str, staff_name: str = "Staff") -> ConversationResult:
        """Route a staff !LLM message directly to the LLM."""
        content = f"[Staff member {staff_name}]: {staff_text}"
        self.messages.append({"role": "user", "content": content})

        try:
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
            ]
            result = self._run_tool_loop(api_messages)
        except Exception as e:
            logger.error("Chat response error: %s", e, exc_info=True)
            result = ConversationResult(text=f"Error: {e}")

        stored_text = result.text
        if result.images:
            stored_text += f"\n\n[{len(result.images)} plot(s) generated]"
        self.messages.append({"role": "assistant", "content": stored_text})

        return result

    def buffer_staff_message(self, staff_text: str, staff_name: str = "Staff"):
        """Buffer a staff message for inclusion as context in the next user message."""
        self._staff_buffer.append(f"[Staff member {staff_name}]: {staff_text}")

    def get_history(self) -> list[dict]:
        """Return the conversation history."""
        return list(self.messages)
