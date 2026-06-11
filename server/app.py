"""BeamtimeHero — FastAPI application.

Web chat interface for synchrotron beamline users with LLM (via
`claude -p --resume`) + Slack staff bridge.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# Add server/ to path for sibling imports, and project root so
# `beamline_tools` is importable.
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from datetime import datetime

from config import BASE_PATH, STATIC_DIR, PROJECT_ROOT, CLAUDE_BIN, llm_configured

# Set BTH env defaults (SPEC_MOCK=0, SPEC_TRANSPORT=screen,
# BEAMTIMEHERO_DATA_DIR) before any subprocess is spawned. The `claude -p`
# subprocess inherits os.environ, and the upstream CLI reads these at
# import time.
import beamline_tools.config  # noqa: F401

import threading

from claude_cli_backend import ClaudeCLIClient
from conversation import ConversationService, new_message_id
from slack_bridge import SlackBridge

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Global state ---
slack_bridge = SlackBridge()
claude_client = ClaudeCLIClient()
conversation: ConversationService | None = None
connected_ws: set[WebSocket] = set()
_event_loop: asyncio.AbstractEventLoop | None = None


def _on_tool_start(names: list[str]):
    _broadcast({"type": "tool_status", "tools": names})


def _new_conversation() -> ConversationService:
    return ConversationService(client=claude_client, on_tool_start=_on_tool_start)


def _swap_conversation() -> ConversationService | None:
    """Replace the global conversation, waiting out any in-flight turn.

    Retiring the old conversation blocks until a running turn finishes,
    then drops the manifest, so the new conversation never races a
    stale persist.
    """
    global conversation

    old = conversation
    if old is not None:
        old.retire()
    else:
        ConversationService.clear_state()
    conversation = _new_conversation() if llm_configured() else None
    return conversation


async def broadcast_ws(message: dict):
    """Send a message to all connected WebSocket clients."""
    payload = json.dumps(message)
    disconnected = set()
    # Copy: the set mutates when clients (dis)connect during the awaits.
    for ws in list(connected_ws):
        try:
            await ws.send_text(payload)
        except Exception:
            disconnected.add(ws)
    connected_ws.difference_update(disconnected)


def _broadcast(msg: dict):
    """Schedule a WebSocket broadcast from any thread."""
    if _event_loop is None:
        logger.warning("No event loop available for WebSocket broadcast")
        return
    fut = asyncio.run_coroutine_threadsafe(broadcast_ws(msg), _event_loop)

    def _log_failure(f):
        exc = f.exception()
        if exc is not None:
            logger.warning("WebSocket broadcast failed: %s", exc)

    fut.add_done_callback(_log_failure)


def on_staff_message(text: str, staff_name: str):
    """Called by SlackBridge when staff sends a message in the #users channel.

    Pure relay — just forward to the web UI, no LLM involved.
    """
    _broadcast({
        "type": "staff_message", "id": new_message_id(),
        "name": staff_name, "text": text,
    })


def on_llm_thread_reply(text: str, staff_name: str):
    """Called by SlackBridge when staff replies in a #llm channel thread.

    Staff message joins the LLM conversation — displayed in the AI pane,
    routed to the LLM, and response posted back to Slack. Runs on the
    Slack Bolt thread; the conversation's turn lock serializes it against
    web turns.
    """
    staff_mid = new_message_id()
    _broadcast({
        "type": "staff_in_llm", "id": staff_mid, "name": staff_name, "text": text,
    })

    if conversation:
        result = conversation.handle_staff_llm(
            text, staff_name, source="slack_llm_thread", message_id=staff_mid
        )
        _broadcast({
            "type": "assistant",
            "id": result.message_id,
            "text": result.text,
            "images": result.images,
        })
        slack_bridge.post_llm_response(result.text)


# --- Staff DM conversations (independent from web app) ---
_dm_conversations: dict[str, ConversationService] = {}
_dm_lock = threading.Lock()


def on_dm_message(text: str, staff_name: str, dm_thread_key: str):
    """Called by SlackBridge when staff DMs the bot.

    Each DM thread gets its own conversation session.
    """
    with _dm_lock:
        if dm_thread_key not in _dm_conversations:
            if not llm_configured():
                logger.warning("Cannot handle DM: gateway not configured")
                return
            # No web broadcast or manifest for DM side-conversations.
            _dm_conversations[dm_thread_key] = ConversationService(
                client=claude_client, persist=False
            )
            logger.info(
                "New DM conversation for %s (key: %s)", staff_name, dm_thread_key
            )
        dm_conversation = _dm_conversations[dm_thread_key]

    try:
        result = dm_conversation.handle_staff_llm(text, staff_name, source="slack_dm")
    except Exception as e:
        logger.error("DM conversation error: %s", e, exc_info=True)
        result_text = f"Error: {e}"
    else:
        result_text = result.text

    # Reply in the DM thread
    channel, thread_ts = dm_thread_key.split(":", 1)
    slack_bridge.post_dm_reply(channel, thread_ts, result_text)


def on_setdir(dir_name: str) -> str:
    """Called by SlackBridge when staff sends !setdir.

    Changes the scan directory and resets the conversation.
    """
    from beamline_tools import config as bl_config
    from beamtimehero_cli.spec_data import local_data as bl_local_data

    bl_config.set_scan_dir(dir_name)
    bl_local_data.clear_cache()

    # Subprocess invocations of `claude -p` re-read BL_SCAN_DIR from env;
    # publish the new value so the next turn's tool calls see it.
    new_dir = bl_config.get_scan_dir()
    os.environ["BL_SCAN_DIR"] = str(new_dir)

    # Reset conversation (same as browser reset)
    _swap_conversation()
    slack_bridge.reset_thread()
    _broadcast({"type": "reset"})

    # Tool subprocesses re-resolve BL_SCAN_DIR at import: a dir whose name
    # doesn't match YYYY-mm_* (and has no matching subdir) silently falls
    # back to upstream's packaged sample data there, even though
    # set_scan_dir accepted it in this process. Warn instead of lying.
    name_ok = re.match(r"\d{4}-\d{2}_", new_dir.name)
    has_dated_subdir = any(
        d.is_dir() and re.match(r"\d{4}-\d{2}_", d.name)
        for d in new_dir.iterdir()
    )
    if not name_ok and not has_dated_subdir:
        return (
            f":warning: `{new_dir}` was set, but its name does not match "
            "`YYYY-mm_*` and it has no such subdirectory — tool calls "
            "re-resolve the scan dir and will fall back to packaged DEMO "
            "data. Rename the directory or pick a `YYYY-mm_*` one. "
            "Conversation reset."
        )
    return f"Scan directory set to `{new_dir}`. Conversation reset."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Slack bridge on startup."""
    global conversation, _event_loop

    # Store the event loop reference for cross-thread broadcasts
    _event_loop = asyncio.get_running_loop()

    # Register BTH's reference docs once at startup (idempotent); the
    # /api/tools handler reads the registry on every request.
    from beamline_tools.cli import register_refdocs
    register_refdocs()

    # Initialize conversation service
    if llm_configured():
        if not claude_client.health_check():
            logger.error(
                "`claude` binary not callable at %r — set CLAUDE_BIN or install Claude Code",
                CLAUDE_BIN,
            )
        try:
            # Resume the previous conversation if a manifest survives the
            # restart — Claude Code's session store still has the context.
            conversation = ConversationService.from_state(
                client=claude_client, on_tool_start=_on_tool_start
            ) or _new_conversation()
            logger.info("LLM conversation service initialized (session=%s)", conversation.session_id)
        except Exception as e:
            logger.error("Failed to initialize conversation service: %s", e)
    else:
        logger.warning("LLM_GATEWAY not configured (no API key for selected gateway)")

    # Start Slack bridge
    slack_bridge.set_staff_callback(on_staff_message)
    slack_bridge.set_llm_thread_callback(on_llm_thread_reply)
    slack_bridge.set_dm_callback(on_dm_message)
    slack_bridge.set_setdir_callback(on_setdir)
    slack_bridge.start()

    yield


# --- FastAPI app ---
app = FastAPI(title="BeamtimeHero", lifespan=lifespan)

# Mount static files at the base path
app.mount(
    f"{BASE_PATH}/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


@app.get(f"{BASE_PATH}/health")
async def health():
    from beamtimehero_cli import config as _cli_config

    return {
        "status": "ok",
        "llm_configured": llm_configured(),
        "claude_binary": await asyncio.to_thread(claude_client.health_check),
        "scan_dir": str(_cli_config.BL_SCAN_DIR),
        "logs_dir": str(_cli_config.BL_LOGS_DIR),
        "using_sample_data": _cli_config.USING_SAMPLE_DATA,
        "using_sample_logs": _cli_config.USING_SAMPLE_LOGS,
    }


async def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
    )


# Register index at BASE_PATH. The bare path redirects to the trailing
# slash so the page's relative asset URLs (static/...) resolve under
# BASE_PATH. When BASE_PATH is empty, only "/" is registered (FastAPI
# rejects "").
if BASE_PATH:
    async def _index_redirect():
        return RedirectResponse(url=f"{BASE_PATH}/")

    app.get(BASE_PATH)(_index_redirect)
    app.get(f"{BASE_PATH}/")(index)
else:
    app.get("/")(index)


def _run_web_turn(conv: ConversationService, user_text: str, user_mid: str) -> dict:
    """Slack-mirror + LLM turn + broadcasts. Blocking — runs off-loop.

    All clients (including the sender) receive the user/assistant events
    over the WebSocket; the sender minted `user_mid` so its own immediate
    render dedups against the broadcast.
    """
    _broadcast({"type": "user", "id": user_mid, "text": user_text})
    slack_bridge.post_user_message(user_text)

    result = conv.handle_message(user_text, source="web", message_id=user_mid)

    _broadcast({
        "type": "assistant",
        "id": result.message_id,
        "text": result.text,
        "images": result.images,
    })
    slack_bridge.post_llm_response(result.text)

    return {
        "response": result.text,
        "images": result.images,
        "id": result.message_id,
        "user_id": user_mid,
    }


@app.post(f"{BASE_PATH}/api/chat")
async def chat(payload: dict):
    """Handle a user chat message."""
    global conversation

    user_text = payload.get("message", "").strip()
    if not user_text:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    raw_id = payload.get("id", "")
    user_mid = raw_id if (
        isinstance(raw_id, str) and raw_id.isalnum() and len(raw_id) <= 64
    ) else new_message_id()

    if not conversation:
        if not llm_configured():
            return JSONResponse(
                {"error": "LLM gateway not configured"}, status_code=503
            )
        conversation = _new_conversation()

    # Off-loop: the turn blocks on a `claude` subprocess for up to minutes;
    # running it here would freeze the WebSocket and every other client.
    return await asyncio.to_thread(_run_web_turn, conversation, user_text, user_mid)


@app.get(f"{BASE_PATH}/api/history")
async def history():
    """Return the display log so clients can render/replay the transcript."""
    if not conversation:
        return {"messages": []}
    return {"messages": conversation.get_history()}


# Sidebar category order + membership. Tools not listed here fall under "Other".
TOOL_CATEGORIES = [
    (
        "Scan Data & Analysis",
        [
            "get_latest_scan", "list_scans", "read_scan",
            "get_active_counter", "get_scan_deadtime",
            "normalize_scan", "average_scans",
            "analyze_convergence", "analyze_efficiency",
            "analyze_feature_evolution", "analyze_per_spot",
            "group_scans_by_spot",
        ],
    ),
    (
        "Plots",
        [
            "plot_scan", "plot_averaged_scans", "plot_data",
            "plot_scan_stack", "plot_first_half_vs_second_half",
            "plot_running_average", "plot_feature_evolution",
        ],
    ),
    (
        "Beamline Logs",
        ["get_latest_log_entries", "search_logs", "list_logs"],
    ),
    (
        "Files & Macros",
        [
            "list_files", "read_file", "write_summary",
            "write_macro", "evaluate_spec_macro", "save_plan",
        ],
    ),
    (
        "SPEC State (read-only)",
        [
            "get_motor_config", "get_counter_config",
            "read_all_positions", "read_motor_position",
            "get_current_datafile", "get_scan_number",
            "get_beam_status", "get_beam_size",
            "get_counts", "get_counter",
            "get_element", "get_anchor", "get_plotselected_counter",
        ],
    ),
]


@app.get(f"{BASE_PATH}/api/tools")
async def get_tools():
    """Return available tools (grouped by category) and reference docs for the frontend sidebar."""
    from tools import TOOL_DESCRIPTIONS
    from beamtimehero_cli import refdocs

    by_name = TOOL_DESCRIPTIONS

    categorized = []
    seen = set()
    for category, names in TOOL_CATEGORIES:
        items = [
            {"name": n, "description": by_name[n]} for n in names if n in by_name
        ]
        seen.update(item["name"] for item in items)
        if items:
            categorized.append({"category": category, "tools": items})

    # Any tool not assigned to a category goes here so nothing is silently hidden.
    leftover = [
        {"name": n, "description": d} for n, d in by_name.items() if n not in seen
    ]
    if leftover:
        categorized.append({"category": "Other", "tools": leftover})

    references = [
        {"name": name, "description": description}
        for name, description in refdocs.list_docs()
    ]
    return {"categories": categorized, "references": references}


@app.post(f"{BASE_PATH}/api/reset")
async def reset():
    """Reset the conversation (destroys the shared session for everyone)."""
    # Off-loop: swapping waits for any in-flight turn to finish.
    await asyncio.to_thread(_swap_conversation)
    slack_bridge.reset_thread()
    await broadcast_ws({"type": "reset"})
    return {"status": "reset"}


@app.post(f"{BASE_PATH}/api/staff-message")
async def staff_message(payload: dict):
    """Send a user message directly to beamline staff via Slack."""
    user_text = payload.get("message", "").strip()
    if not user_text:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    # Post to the users Slack channel
    slack_bridge.post_user_to_staff(user_text)

    # Echo back to all WebSocket clients so the sender sees it in the staff pane
    await broadcast_ws({
        "type": "user_to_staff", "id": new_message_id(), "text": user_text,
    })

    return {"status": "sent"}


@app.post(f"{BASE_PATH}/api/suggestion")
async def submit_suggestion(payload: dict):
    """Save a user-submitted suggestion for improving the AI assistant.

    No LLM classification — filename slug is the first 3 alphanumeric words,
    `valid` is 1 unless the text is empty or trivially short.
    """
    raw_text = payload.get("suggestion", "").strip()
    if not raw_text:
        return JSONResponse({"error": "Empty suggestion"}, status_code=400)

    words = re.findall(r"[a-z0-9]+", raw_text.lower())[:3]
    three_word = "_".join(words) or "suggestion"
    three_word = three_word[:30]
    valid = 1 if len(raw_text) >= 10 else 0

    suggestions_dir = PROJECT_ROOT / "user_suggestions"
    suggestions_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"suggestion_{three_word}_{timestamp}.json"

    record = {
        "timestamp": datetime.now().isoformat(),
        "raw_suggestion": raw_text,
        "valid": valid,
    }

    (suggestions_dir / filename).write_text(json.dumps(record, indent=2))
    logger.info("Saved suggestion: %s (valid=%s)", filename, valid)

    return {"status": "saved", "summary": three_word, "valid": valid}


@app.websocket(f"{BASE_PATH}/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket for receiving real-time staff messages from Slack."""
    await ws.accept()
    connected_ws.add(ws)
    logger.info("WebSocket client connected (%d total)", len(connected_ws))

    try:
        while True:
            # Keep connection alive; client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        # Any exit path must drop the socket or broadcasts hit dead peers.
        connected_ws.discard(ws)
        logger.info("WebSocket client disconnected (%d total)", len(connected_ws))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    # Localhost by default (matches run.sh) — the API is unauthenticated
    # and drives an agent with file-read access. Set HOST to expose.
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=port)
