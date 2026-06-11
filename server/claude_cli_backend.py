"""Claude CLI agent backend for BeamtimeHero.

Spawns `claude -p` as a subprocess per turn and parses its stream-JSON
output. Sessions are persisted by Claude Code on disk — we mint a UUID,
pass it as `--session-id` on the first turn and `--resume <uuid>` on
every turn after.

Tool gating lives in `.claude/agents/beamline-bth.md` (persona + tool surface) and `agent.settings.json` (runtime allowlist, loaded by `--settings` so it does not affect any other Claude Code session running in this directory).
This module only:
  - builds the subprocess argv + env
  - feeds the user message in via stream-json on stdin
  - parses tool calls and plot paths out of stream-json on stdout

Per-session plot isolation: each turn sets `BEAMTIMEHERO_PLOTS_DIR` to a
session-scoped directory under `data/.claude/plots/<session_id>/` so the
upstream tool runner writes plots there.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from config import CLAUDE_BIN, PROJECT_ROOT, gateway_config
from mlflow_logging import run as mlflow_run

logger = logging.getLogger(__name__)

CLAUDE_PLOTS_ROOT = Path(
    os.getenv("CLAUDE_PLOTS_ROOT", str(PROJECT_ROOT / "data" / ".claude" / "plots"))
)

# Hard per-turn wall clock. A hung gateway or stuck `claude` process must
# not wedge the conversation forever.
TURN_TIMEOUT_SECONDS = float(os.getenv("BEAMTIMEHERO_TURN_TIMEOUT_SECONDS", "600"))


# =============================================================================
# Client
# =============================================================================

class ClaudeCLIClient:
    """Thin handle around the `claude` binary. Mints session UUIDs and
    runs `claude --version` for healthchecks. State lives on the caller
    (ConversationService) because the same client can drive many sessions.
    """

    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or str(PROJECT_ROOT)

    def create_session(self) -> str:
        """Mint a fresh UUID. Claude Code accepts any UUID via --session-id."""
        return str(uuid.uuid4())

    def health_check(self) -> bool:
        try:
            r = subprocess.run(
                [CLAUDE_BIN, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return r.returncode == 0
        except Exception as e:
            logger.warning("Claude CLI health check failed: %s", e)
            return False


# =============================================================================
# Stream-JSON parsing
# =============================================================================

def _parse_stream_event(line: str) -> Optional[dict]:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _extract_bash_tool_name(input_obj: dict) -> str:
    """Pull a friendly tool name from a Bash tool_use.input.

    The BTH agent invokes `./scripts/beamtimehero bth <subtree> <name> ...`.
    Reduce that to e.g. `tool list-scans` for the status indicator.
    """
    cmd = (input_obj or {}).get("command", "")
    if not isinstance(cmd, str):
        return "Bash"
    tokens = cmd.split()
    # Skip the script invocation prefix to find "bth <subtree> <name>".
    for i, t in enumerate(tokens):
        if t.endswith("beamtimehero") and i + 1 < len(tokens) and tokens[i + 1] == "bth":
            rest = tokens[i + 2 :]
            if len(rest) >= 2 and rest[0] in {"ref", "tool", "spec-read"}:
                return f"{rest[0]} {rest[1]}"
            if rest:
                return rest[0]
            return "bth"
    return tokens[0] if tokens else "Bash"


def _collect_plot_paths_from_tool_result(content_str: str) -> list[str]:
    """A beamtimehero tool that emits plots prints JSON with `plot_path`
    or `image_paths`. Extract those so the frontend can render them.
    """
    paths: list[str] = []
    if not isinstance(content_str, str):
        return paths
    s = content_str.strip()
    if not s.startswith("{"):
        return paths
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return paths
    if not isinstance(data, dict):
        return paths
    if "image_paths" in data and isinstance(data["image_paths"], list):
        paths.extend(p for p in data["image_paths"] if isinstance(p, str))
    elif "plot_path" in data and isinstance(data["plot_path"], str):
        paths.append(data["plot_path"])
    return paths


def _extract_text_blocks(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text", "")
                if t:
                    parts.append(t)
        return "\n".join(parts)
    return ""


# =============================================================================
# Plot helpers
# =============================================================================

def _read_plot_files(paths: list[str]) -> list[str]:
    """base64-encode plot files for inline display."""
    out: list[str] = []
    seen: set[str] = set()
    for p in paths:
        if p in seen:
            continue
        seen.add(p)
        try:
            with open(p, "rb") as f:
                out.append(base64.b64encode(f.read()).decode())
        except (FileNotFoundError, OSError) as e:
            logger.warning("Plot file unreadable: %s (%s)", p, e)
    return out


def _scrape_session_plots_dir(plots_dir: Path, since: float = 0.0) -> list[str]:
    """Fallback: pick up any PNGs the tool wrote that we didn't catch via
    tool_result JSON (e.g. tools whose output format we didn't recognise).

    `since` scopes the scrape to this turn: the directory is per-session
    and accumulates across turns, so without the watermark every earlier
    turn's plots would be re-attached to each new answer.
    """
    if not plots_dir.is_dir():
        return []
    out = []
    for p in sorted(plots_dir.glob("*.png")):
        try:
            if p.stat().st_mtime >= since:
                out.append(str(p))
        except OSError:
            continue
    return out


# =============================================================================
# Gateway env
# =============================================================================

def _gateway_env() -> dict[str, str]:
    """Build the env overrides for the spawned `claude` subprocess.

    Resolves `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` from the
    gateway block; passes the rest of the prefixed vars through
    (e.g. `ANTHROPIC_DEFAULT_SONNET_MODEL`, `DISABLE_PROMPT_CACHING`).
    """
    gw = gateway_config()
    overrides: dict[str, str] = {}
    if gw.get("url"):
        overrides["ANTHROPIC_BASE_URL"] = gw["url"]
    if gw.get("key"):
        overrides["ANTHROPIC_AUTH_TOKEN"] = gw["key"]
    for k, v in (gw.get("env") or {}).items():
        overrides[k] = v
    return overrides


# =============================================================================
# Turn execution
# =============================================================================

def _run_claude(
    *,
    user_text: str,
    session_id: str,
    is_new_session: bool,
    agent: str,
    plots_dir: Path,
    working_dir: str,
    on_tool_start: Optional[Callable[[list[str]], None]] = None,
) -> tuple[str, list[dict], list[str], dict]:
    """Invoke `claude -p` once and parse its stream-JSON output.

    Returns (final_text, tool_calls, image_b64s, usage_stats).
    """
    plots_dir.mkdir(parents=True, exist_ok=True)
    turn_start = time.time()

    argv = [
        CLAUDE_BIN, "-p",
        "--agent", agent,
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        # Runtime allowlist for the embedded agent. Lives in a dedicated
        # file so it does NOT leak into developer sessions running in
        # this dir (./.claude/settings.json is intentionally empty).
        # Path is relative to working_dir (=PROJECT_ROOT).
        "--settings", "agent.settings.json",
        "--verbose",
    ]
    if is_new_session:
        argv.extend(["--session-id", session_id])
    else:
        argv.extend(["--resume", session_id])

    env = os.environ.copy()
    env["BEAMTIMEHERO_PLOTS_DIR"] = str(plots_dir)
    env.update(_gateway_env())

    logger.info(
        "Spawning claude (agent=%s, gateway=%s, session=%s, new=%s)",
        agent, env.get("ANTHROPIC_BASE_URL", "<default>"), session_id, is_new_session,
    )

    stdin_payload = json.dumps({
        "type": "user",
        "message": {"role": "user", "content": user_text},
    }) + "\n"

    proc = subprocess.Popen(
        argv,
        cwd=working_dir,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # Drain stderr concurrently: with stderr=PIPE read only after stdout
    # EOF, a chatty child fills the ~64KB pipe buffer and both processes
    # deadlock.
    stderr_chunks: list[str] = []

    def _drain_stderr():
        try:
            if proc.stderr is not None:
                for line in proc.stderr:
                    stderr_chunks.append(line)
        except Exception:
            pass

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    timed_out = threading.Event()

    def _kill_on_timeout():
        timed_out.set()
        proc.kill()

    watchdog = threading.Timer(TURN_TIMEOUT_SECONDS, _kill_on_timeout)
    watchdog.daemon = True
    watchdog.start()

    result_text: str = ""
    assistant_text_chunks: list[str] = []
    tool_calls: list[dict] = []
    tool_use_by_id: dict[str, dict] = {}
    plot_paths: list[str] = []
    pending_tool_batch: list[str] = []
    usage_stats: dict = {}

    def _flush_tool_batch():
        if pending_tool_batch and on_tool_start:
            try:
                on_tool_start(list(pending_tool_batch))
            except Exception:
                logger.warning("on_tool_start callback raised", exc_info=True)
        pending_tool_batch.clear()

    try:
        assert proc.stdin is not None
        try:
            proc.stdin.write(stdin_payload)
            proc.stdin.flush()
            proc.stdin.close()
        except BrokenPipeError:
            pass

        assert proc.stdout is not None
        for raw_line in proc.stdout:
            evt = _parse_stream_event(raw_line)
            if not evt:
                continue

            etype = evt.get("type", "")

            if etype == "assistant":
                msg = evt.get("message", {}) or {}
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text":
                            t = block.get("text", "")
                            if t:
                                assistant_text_chunks.append(t)
                        elif btype == "tool_use":
                            tid = block.get("id", "")
                            tname = block.get("name", "")
                            tinput = block.get("input", {}) or {}
                            display_name = (
                                _extract_bash_tool_name(tinput) if tname == "Bash" else tname
                            )
                            record = {
                                "name": display_name,
                                "raw_name": tname,
                                "input": tinput,
                                "output": "",
                            }
                            tool_use_by_id[tid] = record
                            tool_calls.append(record)
                            pending_tool_batch.append(display_name)
                _flush_tool_batch()

            elif etype == "user":
                # tool_result blocks arrive wrapped in user messages.
                msg = evt.get("message", {}) or {}
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_result":
                            continue
                        tid = block.get("tool_use_id", "")
                        raw_content = block.get("content", "")
                        text_content = _extract_text_blocks(raw_content) or (
                            raw_content if isinstance(raw_content, str) else ""
                        )
                        if tid in tool_use_by_id:
                            tool_use_by_id[tid]["output"] = text_content
                        plot_paths.extend(_collect_plot_paths_from_tool_result(text_content))

            elif etype == "result":
                result_text = evt.get("result") or ""
                if evt.get("is_error"):
                    logger.warning("Claude reported result-level error: %s", evt)
                usage_stats = {
                    k: evt[k]
                    for k in ("total_cost_usd", "duration_ms", "num_turns")
                    if k in evt
                }
                usage = evt.get("usage")
                if isinstance(usage, dict):
                    for k in ("input_tokens", "output_tokens",
                              "cache_read_input_tokens", "cache_creation_input_tokens"):
                        if isinstance(usage.get(k), (int, float)):
                            usage_stats[k] = usage[k]

            elif etype == "system" and evt.get("subtype") == "init":
                logger.debug("Claude session init: %s", evt.get("session_id"))

        _flush_tool_batch()
        rc = proc.wait()
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        stderr_thread.join(timeout=5)

    stderr_text = "".join(stderr_chunks)

    if timed_out.is_set():
        raise RuntimeError(
            f"claude turn timed out after {TURN_TIMEOUT_SECONDS:.0f}s and was killed"
        )
    if rc != 0:
        snippet = stderr_text.strip()[:500] or "<empty stderr>"
        raise RuntimeError(f"claude exited with code {rc}: {snippet}")

    final_text = result_text or "\n".join(assistant_text_chunks)

    plot_paths.extend(_scrape_session_plots_dir(plots_dir, since=turn_start))
    images = _read_plot_files(plot_paths)

    return final_text, tool_calls, images, usage_stats


# =============================================================================
# Public turn wrapper (MLflow-instrumented)
# =============================================================================

def send_and_collect(
    client: ClaudeCLIClient,
    session_id: str,
    user_text: str,
    *,
    source: str,
    is_new_session: bool,
    agent: str = "beamline-bth",
    staff_name: Optional[str] = None,
    on_tool_start: Optional[Callable[[list[str]], None]] = None,
) -> tuple[str, list[dict], list[str]]:
    """Run one user turn through `claude -p`.

    `is_new_session` selects `--session-id` (first turn) vs `--resume`
    (subsequent turns). Caller owns the flag because session state needs
    to survive whatever the caller's process model is.
    """
    plots_dir = CLAUDE_PLOTS_ROOT / session_id

    with mlflow_run(
        experiment="bth/agent",
        run_name=f"turn-{int(time.time())}",
        source=source,
    ) as r:
        t0 = time.time()
        text, tools, images, stats = _run_claude(
            user_text=user_text,
            session_id=session_id,
            is_new_session=is_new_session,
            agent=agent,
            plots_dir=plots_dir,
            working_dir=client.working_dir,
            on_tool_start=on_tool_start,
        )

        if r is not None:
            try:
                import mlflow

                mlflow.log_param("backend", "claude_cli")
                mlflow.log_param("source", source)
                mlflow.log_param("agent", agent)
                if staff_name:
                    mlflow.log_param("staff_name", staff_name)

                mlflow.log_metric("claude_cli_latency_seconds", time.time() - t0)
                mlflow.log_metric("tool_call_count", len(tools))
                mlflow.log_metric("images_generated", len(images))
                for stat_name, stat_value in stats.items():
                    if isinstance(stat_value, (int, float)):
                        mlflow.log_metric(stat_name, stat_value)

                per_tool: dict[str, int] = {}
                for c in tools:
                    per_tool[c["name"]] = per_tool.get(c["name"], 0) + 1
                for name_, n in per_tool.items():
                    mlflow.set_tag(f"tool:{name_}", str(n))

                mlflow.set_tag("user_text_preview", str(user_text)[:200])
                mlflow.log_text(user_text, "user_message.txt")
                mlflow.log_text(text or "", "assistant_response.md")
                mlflow.log_dict(
                    {
                        "calls": [
                            {
                                "name": c["name"],
                                "raw_name": c.get("raw_name"),
                                "input": c.get("input", {}),
                                "output_preview": str(c.get("output", ""))[:2048],
                                "output_size": len(str(c.get("output", ""))),
                            }
                            for c in tools
                        ]
                    },
                    "tool_calls.json",
                )
                # Only this turn's plots — the dir is per-session and
                # accumulates across turns.
                for plot_file in _scrape_session_plots_dir(plots_dir, since=t0):
                    mlflow.log_artifact(plot_file, artifact_path="plots")
            except Exception:
                logger.warning("MLflow logging failed in claude_cli seam", exc_info=True)

        return text, tools, images
