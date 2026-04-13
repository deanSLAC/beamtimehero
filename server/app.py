"""BeamtimeHero — FastAPI application.

Web chat interface for synchrotron beamline users with LLM + Slack staff bridge.
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
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add server/ to path for sibling imports
sys.path.insert(0, str(Path(__file__).parent))

import re
from datetime import datetime

import requests

from config import BASE_PATH, STATIC_DIR, API_KEY, API_BASE_URL, PROJECT_ROOT

# Add beamline_lib so blmcp / bldata_analysis / db_connection are importable
sys.path.insert(0, str(Path(__file__).parent.parent / "beamline_lib"))
from api_client import StanfordAPIClient
from conversation import ConversationService
from slack_bridge import SlackBridge

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Global state ---
slack_bridge = SlackBridge()
conversation: ConversationService | None = None
connected_ws: set[WebSocket] = set()
_event_loop: asyncio.AbstractEventLoop | None = None


async def broadcast_ws(message: dict):
    """Send a message to all connected WebSocket clients."""
    payload = json.dumps(message)
    disconnected = set()
    for ws in connected_ws:
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
    asyncio.run_coroutine_threadsafe(broadcast_ws(msg), _event_loop)


def on_staff_message(text: str, staff_name: str):
    """Called by SlackBridge when staff sends a message in the #users channel.

    Pure relay — just forward to the web UI, no LLM involved.
    """
    _broadcast({"type": "staff_message", "name": staff_name, "text": text})


def on_llm_thread_reply(text: str, staff_name: str):
    """Called by SlackBridge when staff replies in a #llm channel thread.

    Staff message joins the LLM conversation — displayed in the AI pane,
    routed to the LLM, and response posted back to Slack.
    """
    # Show staff message in the AI Assistant pane (part of that conversation)
    _broadcast({"type": "staff_in_llm", "name": staff_name, "text": text})

    if conversation:
        result = conversation.handle_staff_llm(text, staff_name)
        _broadcast({
            "type": "assistant",
            "text": result.text,
            "images": result.images,
        })
        slack_bridge.post_llm_response(result.text)


# --- Staff DM conversations (independent from web app) ---
_dm_conversations: dict[str, ConversationService] = {}


def on_dm_message(text: str, staff_name: str, dm_thread_key: str):
    """Called by SlackBridge when staff DMs the bot.

    Each DM thread gets its own conversation session.
    """
    global _dm_conversations

    if dm_thread_key not in _dm_conversations:
        if not API_KEY:
            logger.warning("Cannot handle DM: API_KEY not configured")
            return
        client = StanfordAPIClient()
        _dm_conversations[dm_thread_key] = ConversationService(client)
        logger.info("New DM conversation for %s (key: %s)", staff_name, dm_thread_key)

    dm_conversation = _dm_conversations[dm_thread_key]

    try:
        result = dm_conversation.handle_staff_llm(text, staff_name)
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
    global conversation

    import bl_config
    from local_data import clear_cache

    bl_config.set_scan_dir(dir_name)
    clear_cache()

    # Reset conversation (same as browser reset)
    if API_KEY:
        client = StanfordAPIClient()
        conversation = ConversationService(client)
    slack_bridge.reset_thread()

    return f"Scan directory set to `{bl_config.BL_SCAN_DIR}`. Conversation reset."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Slack bridge on startup."""
    global conversation, _event_loop

    # Store the event loop reference for cross-thread broadcasts
    _event_loop = asyncio.get_running_loop()

    # Initialize conversation service
    if API_KEY:
        try:
            client = StanfordAPIClient()
            conversation = ConversationService(client)
            logger.info("LLM conversation service initialized")
        except Exception as e:
            logger.error("Failed to initialize LLM client: %s", e)

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
    return {"status": "ok"}


async def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
    )


# Register index at BASE_PATH (with and without trailing slash).
# When BASE_PATH is empty, only "/" is registered (FastAPI rejects "").
if BASE_PATH:
    app.get(BASE_PATH)(index)
    app.get(f"{BASE_PATH}/")(index)
else:
    app.get("/")(index)


@app.post(f"{BASE_PATH}/api/chat")
async def chat(payload: dict):
    """Handle a user chat message."""
    global conversation

    user_text = payload.get("message", "").strip()
    if not user_text:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    if not conversation:
        if not API_KEY:
            return JSONResponse(
                {"error": "API_KEY not configured"}, status_code=503
            )
        client = StanfordAPIClient()
        conversation = ConversationService(client)

    # Forward user message to Slack
    slack_bridge.post_user_message(user_text)

    # Get LLM response
    result = conversation.handle_message(user_text)

    # Forward LLM response to Slack
    slack_bridge.post_llm_response(result.text)

    return {"response": result.text, "images": result.images}


@app.get(f"{BASE_PATH}/api/tools")
async def get_tools():
    """Return available tools and reference docs for the frontend sidebar."""
    from tools import TOOL_DEFINITIONS
    from tools.cli import REFERENCE_DOCS

    tools = [
        {"name": t["function"]["name"], "description": t["function"]["description"]}
        for t in TOOL_DEFINITIONS
    ]
    references = [
        {"name": name, "description": doc["description"]}
        for name, doc in REFERENCE_DOCS.items()
    ]
    return {"tools": tools, "references": references}


@app.post(f"{BASE_PATH}/api/reset")
async def reset():
    """Reset the conversation."""
    global conversation

    if API_KEY:
        client = StanfordAPIClient()
        conversation = ConversationService(client)

    slack_bridge.reset_thread()
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
    await broadcast_ws({"type": "user_to_staff", "text": user_text})

    return {"status": "sent"}


@app.post(f"{BASE_PATH}/api/suggestion")
async def submit_suggestion(payload: dict):
    """Accept an LLM upgrade suggestion, classify it via LLM, and save."""
    raw_text = payload.get("suggestion", "").strip()
    if not raw_text:
        return JSONResponse({"error": "Empty suggestion"}, status_code=400)

    if not API_KEY:
        return JSONResponse({"error": "API_KEY not configured"}, status_code=503)

    classification_prompt = (
        "You are a classifier. The user has submitted a suggestion for improving an AI assistant. "
        "Analyze the suggestion and return ONLY valid JSON with these fields:\n"
        '- "summary_3word": a 3-word summary (lowercase, underscores instead of spaces)\n'
        '- "summary_2sentence": a 2-sentence summary (include ONLY if the suggestion is longer than 5 sentences, otherwise set to null)\n'
        '- "valid": 1 if this is a genuine, actionable suggestion, 0 if it is blank, gibberish, a single character, or not a real suggestion\n'
        "Return ONLY the JSON object, no markdown fencing."
    )

    messages = [
        {"role": "system", "content": classification_prompt},
        {"role": "user", "content": raw_text},
    ]

    try:
        client = StanfordAPIClient()
        url = f"{API_BASE_URL}/chat/completions"
        req_payload = {
            "model": client.model,
            "messages": messages,
            "temperature": 0.1,
        }
        response = requests.post(
            url, headers=client._get_headers(), json=req_payload, timeout=60
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]

        # Strip markdown fences if present
        content = re.sub(r"^```json\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())
        parsed = json.loads(content)
    except Exception as e:
        logger.error("Suggestion classification failed: %s", e, exc_info=True)
        return JSONResponse({"error": "Failed to classify suggestion"}, status_code=500)

    # Save to disk
    suggestions_dir = PROJECT_ROOT / "user_suggestions"
    suggestions_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    three_word = parsed.get("summary_3word", "unknown")
    three_word = re.sub(r"[^a-z0-9_]", "", three_word.lower().replace(" ", "_"))[:30]
    filename = f"suggestion_{three_word}_{timestamp}.json"

    record = {
        "timestamp": datetime.now().isoformat(),
        "raw_suggestion": raw_text,
        "summary_2sentence": parsed.get("summary_2sentence"),
        "valid": parsed.get("valid", 0),
    }

    (suggestions_dir / filename).write_text(json.dumps(record, indent=2))
    logger.info("Saved suggestion: %s (valid=%s)", filename, record["valid"])

    return {"status": "saved", "summary": three_word, "valid": record["valid"]}


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
        connected_ws.discard(ws)
        logger.info("WebSocket client disconnected (%d total)", len(connected_ws))


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
