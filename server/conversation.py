"""Conversation service for BeamtimeHero.

Manages message history and LLM interaction with tool-use support.
Supports two tool modes:
- MCP: Native function-calling with full tool schemas
- CLI: Single run_command tool with progressive discovery
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

import bl_config

from api_client import StanfordAPIClient
from config import TOOLS_MODE
from mlflow_logging import run as mlflow_run, decode_b64_png
from tools import TOOL_DEFINITIONS, CLI_TOOL_DEFINITION
from tools.executor import execute_tool
from tools.cli import run_cli

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 20


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

    def _run_tool_loop(
        self,
        messages: list[dict],
        *,
        source: str = "web",
        staff_name: str | None = None,
        user_text_preview: str | None = None,
    ) -> ConversationResult:
        """Run the LLM request with a multi-round tool loop.

        Args:
            messages: Conversation messages (without system message).
            source: One of "web", "slack_llm_thread", "slack_dm" for MLflow tagging.
            staff_name: Slack staff display name when source != "web".
            user_text_preview: First ~200 chars of the user message for MLflow tag.
        """
        tools = self._get_tool_definitions()
        all_images: list[str] = []

        with mlflow_run(
            experiment="bth/chat",
            run_name=f"turn-{int(time.time())}",
            source=source,
        ) as r:
            tool_round = 0
            tool_call_count = 0
            per_tool_counts: dict[str, int] = {}
            tool_calls_log: list[dict] = []
            usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            llm_latency_seconds = 0.0
            error_flag = 0
            response_text = ""

            def _accumulate_usage(api_result: dict) -> None:
                usage = api_result.get("usage") or {}
                for k in usage_total:
                    try:
                        usage_total[k] += int(usage.get(k, 0) or 0)
                    except (TypeError, ValueError):
                        pass

            try:
                t0 = time.perf_counter()
                result = self.client.chat_completion(messages, tools=tools)
                llm_latency_seconds += time.perf_counter() - t0
                _accumulate_usage(result)
                assistant_msg = result["choices"][0]["message"]
                tool_calls = assistant_msg.get("tool_calls")

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

                        tool_call_count += 1
                        per_tool_counts[tool_name] = per_tool_counts.get(tool_name, 0) + 1
                        result_str = tool_result if isinstance(tool_result, str) else str(tool_result)
                        tool_calls_log.append({
                            "round": tool_round,
                            "name": tool_name,
                            "args": tool_args,
                            "result_preview": result_str[:2048],
                            "result_size": len(result_str),
                        })

                        api_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_result,
                        })

                    t0 = time.perf_counter()
                    result = self.client.chat_completion(
                        api_messages, include_context=False, tools=tools
                    )
                    llm_latency_seconds += time.perf_counter() - t0
                    _accumulate_usage(result)
                    assistant_msg = result["choices"][0]["message"]
                    tool_calls = assistant_msg.get("tool_calls")

                response_text = assistant_msg.get("content", "")
            except Exception:
                error_flag = 1
                raise
            finally:
                if r is not None:
                    try:
                        import mlflow

                        mlflow.log_param("model", self.client.model)
                        mlflow.log_param("tools_mode", TOOLS_MODE)
                        mlflow.log_param("scan_dir", str(bl_config.BL_SCAN_DIR))
                        mlflow.log_param("backend", "bth")
                        mlflow.log_param("source", source)
                        if staff_name:
                            mlflow.log_param("staff_name", staff_name)

                        mlflow.log_metric("tool_round_count", tool_round)
                        mlflow.log_metric("tool_call_count", tool_call_count)
                        mlflow.log_metric("images_generated", len(all_images))
                        mlflow.log_metric("prompt_tokens", usage_total["prompt_tokens"])
                        mlflow.log_metric("completion_tokens", usage_total["completion_tokens"])
                        mlflow.log_metric("total_tokens", usage_total["total_tokens"])
                        mlflow.log_metric("llm_latency_seconds", llm_latency_seconds)
                        mlflow.log_metric("error", error_flag)

                        mlflow.set_tag("scan_dir", str(bl_config.BL_SCAN_DIR))
                        for name_, n in per_tool_counts.items():
                            mlflow.set_tag(f"tool:{name_}", str(n))
                        if user_text_preview:
                            mlflow.set_tag("user_text_preview", user_text_preview[:200])
                            mlflow.log_text(user_text_preview, "user_message.txt")
                        mlflow.log_text(response_text or "", "assistant_response.md")
                        mlflow.log_dict({"calls": tool_calls_log}, "tool_calls.json")
                        for i, b64 in enumerate(all_images):
                            try:
                                mlflow.log_image(decode_b64_png(b64), f"plots/plot_{i}.png")
                            except Exception:
                                logger.warning("MLflow log_image failed for plot %d", i, exc_info=True)
                    except Exception:
                        logger.warning("MLflow logging failed in chat seam", exc_info=True)

            return ConversationResult(text=response_text, images=all_images)

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

        try:
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
            ]
            result = self._run_tool_loop(
                api_messages,
                source=source,
                user_text_preview=user_text[:200],
            )
        except Exception as e:
            logger.error("Chat response error: %s", e, exc_info=True)
            result = ConversationResult(text=f"Error: {e}")

        # Store text in history (omit images to keep context lean)
        stored_text = result.text
        if result.images:
            stored_text += f"\n\n[{len(result.images)} plot(s) generated]"
        self.messages.append({"role": "assistant", "content": stored_text})

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

        try:
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in self.messages
            ]
            result = self._run_tool_loop(
                api_messages,
                source=source,
                staff_name=staff_name,
                user_text_preview=staff_text[:200],
            )
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
