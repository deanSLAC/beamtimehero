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

from config import BASE_PATH, STATIC_DIR, API_KEY, PLAYGROUND_ROOT

# Add playground root so blmcp / bldata_analysis / db_connection are importable
sys.path.insert(0, PLAYGROUND_ROOT)
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
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(broadcast_ws(msg), loop)
        else:
            loop.run_until_complete(broadcast_ws(msg))
    except RuntimeError:
        logger.warning("No event loop available for WebSocket broadcast")


def on_staff_message(text: str, staff_name: str):
    """Called by SlackBridge when staff sends a message in Slack."""
    # Check for !LLM flag
    route_to_llm = "!LLM" in text

    if route_to_llm:
        display_text = text.replace("!LLM", "").strip()
    else:
        display_text = text

    # Always show staff message in the chat window
    _broadcast({"type": "staff", "name": staff_name, "text": display_text})

    if conversation:
        if route_to_llm:
            # Route to LLM and broadcast the response
            result = conversation.handle_staff_llm(display_text, staff_name)
            _broadcast({
                "type": "assistant",
                "text": result.text,
                "images": result.images,
            })
            # Also post LLM response back to Slack
            slack_bridge.post_llm_response(result.text)
        else:
            # Buffer for context on the user's next message
            conversation.buffer_staff_message(display_text, staff_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Slack bridge on startup."""
    global conversation

    # Store the event loop reference for cross-thread access
    app.state.loop = asyncio.get_event_loop()

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


@app.get(f"{BASE_PATH}")
@app.get(f"{BASE_PATH}/")
async def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        media_type="text/html",
    )


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


@app.post(f"{BASE_PATH}/api/reset")
async def reset():
    """Reset the conversation."""
    global conversation

    if API_KEY:
        client = StanfordAPIClient()
        conversation = ConversationService(client)

    slack_bridge.reset_thread()
    return {"status": "reset"}


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
