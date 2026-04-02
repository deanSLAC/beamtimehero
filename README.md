# BeamtimeHero

Chat interface for synchrotron beamline users at SSRL. Users ask questions about their experiment through a web UI. Questions are answered by an LLM (via Stanford AI API Gateway) that can query beamline scans, search logs, and generate plots. Conversations are forwarded to a Slack channel where staff can monitor and respond in real time.

## Architecture

```
User (Browser)  <-->  FastAPI Server  <-->  Stanford AI API (LLM)
                           |                       |
                       Slack Bridge           Tool System
                           |               (scans, logs, plots)
                       WebSocket                   |
                           |              blmcp / bldata_analysis
                       Slack Channel              (playground)
                        (Staff)
```

## Tool System

The LLM can call 10 beamline tools during conversation:

| Tool | Purpose |
|------|---------|
| `get_latest_scan` | Most recent scan metadata + data preview |
| `list_scans` | Browse processed scan history |
| `read_scan` | Read a specific scan's data |
| `get_latest_log_entries` | Recent beamline control log output |
| `search_logs` | Search logs for errors or strings |
| `list_logs` | List available log files |
| `get_active_counter` | Detect active fluorescence counter |
| `get_scan_deadtime` | Scan overhead/efficiency stats |
| `plot_scan` | Generate and display a scan plot |
| `plot_data` | General-purpose line chart |

### Two Tool Modes

Set `TOOLS_MODE` to choose how tools are presented to the LLM:

- **`mcp`** (default) — All 10 tool schemas are included in every API request via native function-calling. All context documents are loaded into the system prompt. More reliable tool selection, slightly higher per-request token cost.

- **`cli`** — A single `run_command` tool is defined. The LLM discovers available commands progressively via `beamtimehero --help`. Large reference documents (cryostat procedures, SPEC reference, user guide) are served on-demand via `beamtimehero reference <doc>` instead of being loaded in the system prompt. Lower baseline token cost, 1-2 extra round-trips for tool discovery.

## Project Structure

```
server/               Python FastAPI backend
  app.py              Main server (REST + WebSocket)
  api_client.py       Stanford AI API Gateway client
  conversation.py     LLM conversation management + tool loop
  slack_bridge.py     Bidirectional Slack bridge
  config.py           Shared configuration
  tools/              Tool system
    definitions.py    MCP tool schemas + CLI tool definition
    executor.py       Tool dispatch (calls blmcp.tools)
    cli.py            Argparse CLI for progressive discovery mode
static/               Plain JavaScript frontend
  index.html          Chat interface
  css/style.css       SSRL theme (beige + red accents)
  js/app.js           Chat client with WebSocket + markdown/image rendering
  js/marked.min.js    Markdown parser library
  images/             SSRL logo
context/              Beamline reference documents (injected into system prompt)
k8s/                  Kubernetes deployment manifests
Dockerfile            Container image
```

## Local Development

### Prerequisites

- Python 3.9+
- Access to the `playground` repo (sibling directory by default) for `blmcp` and `bldata_analysis` imports

### Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API_KEY, Slack tokens, PLAYGROUND_ROOT
python server/app.py
```

The app runs on port 8080 at `http://localhost:8080/beamtimehero`.

### Playground dependency

Tool implementations depend on `blmcp` and `bldata_analysis` from the playground repo. Set `PLAYGROUND_ROOT` to point to its location (defaults to `../playground` relative to this project).

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_KEY` | Yes | Stanford AI API Gateway key |
| `STANFORD_MODEL` | No | LLM model (default: `claude-4-5-sonnet`) |
| `SLACK_BOT_TOKEN` | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | No | Slack app-level token (`xapp-...`, for Socket Mode) |
| `SLACK_CHANNEL_ID` | No | Slack channel to post conversations to |
| `BASE_PATH` | No | URL base path (default: `/beamtimehero`) |
| `PLAYGROUND_ROOT` | No | Path to playground repo (default: `../playground`) |
| `TOOLS_MODE` | No | `mcp` (default) or `cli` — see Tool Modes above |

Slack integration is optional — without tokens, the app still works as a standalone LLM chat.

## Kubernetes Deployment

FluxCD watches the container registry and auto-deploys new image tags. The deployment references secrets via `secretKeyRef` — create them once per namespace before the first deploy:

```bash
kubectl create secret generic beamtimehero-secrets \
  --namespace beamtimehero \
  --from-literal=API_KEY=... \
  --from-literal=SLACK_BOT_TOKEN=... \
  --from-literal=SLACK_APP_TOKEN=... \
  --from-literal=SLACK_CHANNEL_ID=...
```

Deployed at `https://isaac.slac.stanford.edu/beamtimehero` (SLAC network only).
