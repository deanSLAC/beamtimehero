# BeamtimeHero

Chat interface for synchrotron beamline users at SSRL BL15-2. Users ask questions about their experiment through a web UI. Questions are answered by an LLM (via Stanford AI API Gateway) that can query beamline scans, search logs, and generate plots. Conversations are forwarded to a Slack channel where staff can monitor and respond in real time.

Runs locally on the beamline computer for direct access to SPEC data files, logs, and (in the future) the SPEC DAQ session.

## Architecture

```
User (Browser)  <-->  FastAPI Server  <-->  Stanford AI API (LLM)
                           |                       |
                       Slack Bridge           Tool System
                           |               (scans, logs, plots)
                       WebSocket                   |
                           |              blmcp / bldata_analysis
                       Slack Channel              (beamline_lib/)
                        (Staff)
```

All data access is local filesystem -- no database required. SPEC data files are read directly via silx, with scan metadata cached in a JSON sidecar for performance. Logs are parsed on demand from SPEC log files.

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

- **`cli`** (default) -- A single `run_command` tool is defined. The LLM discovers available commands progressively via `beamtimehero --help`. Large reference documents are served on-demand instead of in the system prompt.

- **`mcp`** -- All 10 tool schemas are included in every API request via native function-calling. All context documents are loaded into the system prompt.

## Project Structure

```
beamline_lib/         Beamline data packages (self-contained)
  blmcp/              Tool implementations (scan, log, plot operations)
  bldata_analysis/    Data analysis layer (scans, logs, plotting)
  bllogs_converter/   Log parsing (log_parser.py used for on-demand parsing)
  local_data.py       Local filesystem data access via silx (reads SPEC files directly)
  config.py           Beamline configuration (data paths, directories)
server/               Python FastAPI backend
  app.py              Main server (REST + WebSocket)
  api_client.py       Stanford AI API Gateway client
  conversation.py     LLM conversation management + tool loop
  slack_bridge.py     Bidirectional Slack bridge
  config.py           App configuration (API keys, paths, modes)
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
```

## Setup (Beamline Computer)

### Prerequisites

- Python 3.9+
- Access to SPEC data files and logs on the local filesystem

### Install

```bash
git clone <this-repo>
cd beamtimehero
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Edit `.env` and set:
- `API_KEY` -- your Stanford AI API Gateway key (required)
- `BL_SCAN_DIR` -- path to SPEC data files (default: `/sdf/group/ssrl/isaac/data/data`)
- `BL_LOGS_DIR` -- path to SPEC log files (default: `/sdf/group/ssrl/isaac/data/logs`)
- Slack tokens (optional, for staff bridge)

### Run

```bash
source venv/bin/activate
python server/app.py
```

The app serves at `http://localhost:8080/beamtimehero`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_KEY` | Yes | Stanford AI API Gateway key |
| `STANFORD_MODEL` | No | LLM model (default: `claude-4-5-sonnet`) |
| `BL_SCAN_DIR` | No | Path to SPEC data files |
| `BL_LOGS_DIR` | No | Path to SPEC log files |
| `SLACK_BOT_TOKEN` | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | No | Slack app-level token (`xapp-...`, for Socket Mode) |
| `SLACK_CHANNEL_ID` | No | Slack channel to post conversations to |
| `BASE_PATH` | No | URL base path (default: `/beamtimehero`) |
| `TOOLS_MODE` | No | `cli` (default) or `mcp` |

Slack integration is optional -- without tokens, the app still works as a standalone LLM chat.

## Future Capabilities

Running locally on the beamline computer enables features that a remote K8s deployment cannot provide:

- **Macro writing assistance** -- LLM can read/write SPEC macro files on the local filesystem
- **Beamline computer access** -- shell access for troubleshooting, checking processes, software installs
- **DAQ integration** -- direct interaction with the SPEC session (reading live motor positions, queueing scans)
