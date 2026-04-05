# BeamtimeHero

Chat interface for synchrotron beamline users at SSRL BL15-2. Users ask questions about their experiment through a web UI. Questions are answered by an LLM (via Stanford AI API Gateway) that can query beamline scans, search logs, read/write macros, send commands to SPEC, and generate plots. Conversations are mirrored to Slack where staff can monitor, respond, and collaborate in real time.

Runs locally on the beamline computer for direct access to SPEC data files, logs, the SPEC config, and the running SPEC session.

## Architecture

```
User (Browser)  <-->  FastAPI Server  <-->  Stanford AI API (LLM)
                           |                       |
                       Slack Bridge           Tool System
                      /           \          (22 tools)
              #beamtimehero    #users            |
              (LLM log)     (staff-user    beamline_lib/
                             relay)       (scans, logs, plots,
                                          files, SPEC config,
                          Staff DMs        SPEC commands)
                       (independent
                        sessions)
```

All data access is local filesystem -- no database required. SPEC data files are read directly via silx, with scan metadata cached in a JSON sidecar for performance. Logs are parsed on demand from SPEC log files.

## Tool System

The LLM has access to 22 beamline tools:

### Data & Logs
| Tool | Purpose |
|------|---------|
| `get_latest_scan` | Most recent scan metadata + data preview |
| `list_scans` | Browse processed scan history |
| `read_scan` | Read a specific scan's data |
| `get_latest_log_entries` | Recent beamline control log output |
| `search_logs` | Search logs for errors or strings |
| `list_logs` | List available log files |

### Analysis
| Tool | Purpose |
|------|---------|
| `get_active_counter` | Detect active fluorescence counter |
| `get_scan_deadtime` | Scan overhead/efficiency stats |
| `normalize_scan` | Edge-step normalize a scan |
| `average_scans` | Average energy scans with std dev |
| `analyze_convergence` | Check if repeated scans have converged |
| `analyze_efficiency` | Full efficiency report with optimal scan count |

### Plotting
| Tool | Purpose |
|------|---------|
| `plot_scan` | Generate and display a scan plot |
| `plot_averaged_scans` | Overlay averaged scans for multiple samples |
| `plot_data` | General-purpose line chart |

### File Access
| Tool | Purpose |
|------|---------|
| `list_files` | List non-SPEC files in the scan directory (macros, configs) |
| `read_file` | Read a text file from the scan directory |
| `write_summary` | Save a conversation summary as timestamped .txt |
| `write_macro` | Save an edited macro as `<name>_hero-edit_<timestamp>.mac` |

### SPEC Integration
| Tool | Purpose |
|------|---------|
| `get_motor_config` | Motor configuration from SPEC config file |
| `get_counter_config` | Counter configuration from SPEC config file |
| `spec_command` | Send whitelisted commands to the running SPEC session (wa, pwd, fon, get_S) |

### Two Tool Modes

Set `TOOLS_MODE` to choose how tools are presented to the LLM:

- **`cli`** (default) -- A single `run_command` tool is defined. The LLM discovers available commands progressively via `beamtimehero --help`. Large reference documents are served on-demand instead of in the system prompt.

- **`mcp`** -- All tool schemas are included in every API request via native function-calling. All context documents are loaded into the system prompt.

## Slack Integration

Three-channel architecture with a single Slack bot:

- **#beamtimehero** (LLM channel) -- User questions and LLM responses are mirrored here. Staff can reply in thread to join the conversation -- their messages go to the LLM and responses appear in the web UI.
- **#users** (relay channel) -- Pure relay between web app users and staff. No LLM involvement. Users see these in the "Staff Chat" pane.
- **Staff DMs** -- Staff can DM the bot for independent chat sessions, each DM thread gets its own conversation.

Staff can change the active scan directory at runtime via `!setdir 2026-04_Username` in either channel. `!setdir auto` re-detects the newest experiment folder.

## Project Structure

```
beamline_lib/         Beamline data packages (self-contained)
  blmcp/              Tool implementations (scan, log, plot operations)
  bldata_analysis/    Data analysis layer (scans, logs, plotting)
  bllogs_converter/   Log parsing (log_parser.py used for on-demand parsing)
  local_data.py       Local filesystem data access via silx (reads SPEC files directly)
  bl_config.py        Beamline configuration (data paths, mutable scan dir)
  spec_client.py      SPEC session commands via GNU screen injection
  spec_config.py      SPEC motor/counter config file parser
server/               Python FastAPI backend
  app.py              Main server (REST + WebSocket + Slack callbacks)
  api_client.py       Stanford AI API Gateway client
  conversation.py     LLM conversation management + tool loop
  slack_bridge.py     Three-channel Slack bridge + !setdir + staff DMs
  config.py           App configuration (API keys, paths, modes)
  tools/              Tool system
    definitions.py    MCP tool schemas + CLI tool definition
    executor.py       Tool dispatch (calls blmcp.tools + file/spec tools)
    cli.py            Argparse CLI for progressive discovery mode
static/               Plain JavaScript frontend
  index.html          Split-pane chat interface (AI + Staff) with sidebar
  css/style.css       SSRL theme (beige + red accents)
  js/app.js           Chat client with WebSocket + markdown/image rendering
  js/marked.min.js    Markdown parser library
  images/             SSRL logo
context/              Beamline reference documents (system prompt + on-demand)
```

## Setup (Beamline Computer)

### Prerequisites

- Python 3.9+
- Access to SPEC data files and logs on the local filesystem
- GNU screen with a SPEC session named `spec` (for SPEC command tools)

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
- `BL_SCAN_DIR` -- path to SPEC data root (default: `/data/fifteen`, auto-detects newest subfolder)
- `BL_LOGS_DIR` -- path to SPEC log files (default: `/usr/local/lib/spec.log/logfiles`)
- Slack tokens and channel IDs (optional, for staff bridge)

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
| `BL_SCAN_DIR` | No | Path to SPEC data root (default: `/data/fifteen`) |
| `BL_LOGS_DIR` | No | Path to SPEC log files |
| `SLACK_BOT_TOKEN` | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | No | Slack app-level token (`xapp-...`, for Socket Mode) |
| `SLACK_LLM_CHANNEL_ID` | No | Slack channel for user-LLM conversation log |
| `SLACK_USERS_CHANNEL_ID` | No | Slack channel for staff-user communication |
| `BASE_PATH` | No | URL base path (default: `/beamtimehero`) |
| `TOOLS_MODE` | No | `cli` (default) or `mcp` |

Slack integration is optional -- without tokens, the app still works as a standalone LLM chat.
