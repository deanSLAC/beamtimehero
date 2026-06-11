# BeamtimeHero

Chat interface for synchrotron beamline users at SSRL BL15-2. Users ask questions about their experiment through a web UI. Questions are answered by an LLM agent (Claude Code, spawned as a `claude -p --resume` subprocess per turn) that can query beamline scans, search logs, read SPEC state, and generate plots. Conversations are mirrored to Slack where staff can monitor, respond, and collaborate in real time.

Runs locally on the beamline computer for direct access to SPEC data files, logs, the SPEC config, and the running SPEC session.

## Architecture

```
User (Browser)  <-->  FastAPI Server  <-->  claude -p --resume (subprocess per turn)
                           |                       |
                       Slack Bridge          Bash -> ./scripts/beamtimehero
                      /           \                |
              #beamtimehero    #users         bth profile (~42 commands)
              (LLM log)     (staff-user       + ref docs, aliasing the
                             relay)           shared beamtimehero_cli
                                              catalog (scans, logs,
                          Staff DMs           plots, SPEC read-only)
                       (independent
                        sessions)
```

All data access is local filesystem -- no database required. SPEC data files are read directly via silx through the shared `beamtimehero_cli` package; logs are parsed on demand from SPEC log files.

## Tool System

The agent is Claude Code running the `beamline-bth` persona (`.claude/agents/beamline-bth.md`). It has no in-process tools; it shells into two flat CLI trees via Bash:

```
beamtimehero ref --list                  # list reference docs
beamtimehero ref <name>                  # fetch a doc (procedures, SPEC reference)
beamtimehero bth --help                  # discover every agent command
beamtimehero bth <leaf> [--flag ...]     # e.g. bth list-scans, bth plot-scan,
                                         #      bth read-motor-position
```

The `bth` leaves are curated aliases declared in `beamline_tools/bth_profile.py`, each pointing at a canonical tool in the upstream `beamtimehero_cli` catalog. They cover scan data and analysis, plotting, beamline logs, file/macro access, and read-only SPEC state.

Tool access is gated in two independent layers:

1. **Parse-time** -- `build_parser()` in `beamline_tools/cli.py` registers only the `ref` and `bth` trees; the canonical trees (`spec-write`, `db`, ...) cannot even be parsed by the agent-facing binary. Operators can set `BEAMTIMEHERO_FULL_CLI=1` at a terminal to restore the full upstream catalog.
2. **Permission-time** -- `agent.settings.json` deny rules and the agent frontmatter allowlist (Bash restricted to `beamtimehero bth *` / `ref *`, Read restricted to `context/**` and `data/**`).

## Slack Integration

Three-channel architecture with a single Slack bot:

- **#beamtimehero** (LLM channel) -- User questions and LLM responses are mirrored here. Staff can reply in thread to join the conversation -- their messages go to the LLM and responses appear in the web UI.
- **#users** (relay channel) -- Pure relay between web app users and staff. No LLM involvement. Users see these in the "Staff Chat" pane.
- **Staff DMs** -- Staff can DM the bot for independent chat sessions, each DM thread gets its own conversation.

Staff can change the active scan directory at runtime via `!setdir 2026-04_Username` from either staff channel or a DM (other channels are ignored). `!setdir auto` re-detects the newest experiment folder. Changing the directory resets the conversation.

## Project Structure

```
beamline_tools/       BTH extension layer over the shared beamtimehero_cli package
  cli.py              Agent-facing CLI: ref + bth trees, parse-time gating
  bth_profile.py      Curated agent profile (the bth aliases)
  config.py           Env defaults for the live beamline host (SPEC_MOCK=0, screen)
scripts/beamtimehero  Thin shell wrapper around beamline_tools.cli:main
server/               Python FastAPI backend
  app.py              Main server (REST + WebSocket + Slack callbacks)
  claude_cli_backend.py  Spawns `claude -p` per turn, parses stream-JSON output
  conversation.py     Session lifecycle, turn serialization, transcript persistence
  slack_bridge.py     Three-channel Slack bridge + !setdir + staff DMs
  config.py           App configuration (gateway selection, paths)
  tools/              Sidebar tool descriptions (derived from the bth profile)
static/               Plain JavaScript frontend (no build step)
  index.html          Split-pane chat interface (AI + Staff) with sidebar
  css/style.css       SSRL theme (beige + red accents)
  js/app.js           Chat client: WebSocket events, history replay, sanitized markdown
  js/marked.min.js    Markdown parser library
  js/purify.min.js    DOMPurify HTML sanitizer
  images/             SSRL logo
context/              Beamline reference documents (served via `beamtimehero ref`)
.claude/agents/       The beamline-bth agent persona
tests/                pytest suite (CLI gating, profile surface, turn serialization,
                      session recovery)
```

## Setup (Beamline Computer)

### Prerequisites

- Python 3.10+ (the venv on the beamline host runs 3.13)
- The `claude` CLI (Claude Code) on PATH
- The shared CLI package checked out as a sibling: `../beamtimehero_cli` (installed editably by requirements.txt)
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
- `LLM_GATEWAY` -- which gateway Claude Code routes through: `stanford`, `slac`, or `default` (a locally-authenticated `claude` binary, no key needed)
- `STANFORD_API_KEY` / `SLAC_API_KEY` -- the key for the chosen gateway
- `BL_SCAN_DIR` -- path to SPEC data root (default: `/data/fifteen`, auto-detects newest `YYYY-mm_*` subfolder)
- `BL_LOGS_DIR` -- path to SPEC log files (default: `/usr/local/lib/spec.log/logfiles`)
- Slack tokens and channel IDs (optional, for staff bridge)

### Run

```bash
./run.sh                 # http://localhost:8742/ (localhost only)
# or
source venv/bin/activate
python server/app.py     # http://localhost:8080/
```

The server binds `127.0.0.1` by default -- the API is unauthenticated, so set `HOST` deliberately if you need to expose it.

Tests: `venv/bin/python -m pytest tests/`

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_GATEWAY` | No | `stanford`, `slac`, or `default` (default: `default`) |
| `STANFORD_API_KEY` / `SLAC_API_KEY` | For named gateways | API key for the selected gateway |
| `CLAUDE_BIN` | No | Path to the `claude` binary (default: `claude` on PATH) |
| `BL_SCAN_DIR` | No | Path to SPEC data root (default: `/data/fifteen`) |
| `BL_LOGS_DIR` | No | Path to SPEC log files |
| `SLACK_BOT_TOKEN` | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | No | Slack app-level token (`xapp-...`, for Socket Mode) |
| `SLACK_LLM_CHANNEL_ID` | No | Slack channel for user-LLM conversation log |
| `SLACK_USERS_CHANNEL_ID` | No | Slack channel for staff-user communication |
| `BASE_PATH` | No | URL base path (default: empty, i.e. served at `/`) |
| `PORT` / `HOST` | No | Bind address (defaults: `8080` / `127.0.0.1`; `run.sh` uses `8742`) |
| `BEAMTIMEHERO_DATA_DIR` | No | Data dir for plots + the persisted conversation manifest (default: `./data/`) |
| `BEAMTIMEHERO_TURN_TIMEOUT_SECONDS` | No | Hard wall clock per `claude -p` turn (default: `600`) |
| `BEAMTIMEHERO_FULL_CLI` | No | Operator-only: `1` exposes the full upstream CLI catalog at a terminal |
| `MLFLOW_ENABLED` / `MLFLOW_TRACKING_URI` / `MLFLOW_TRACKING_TOKEN` | No | Best-effort MLflow tracing (disabled by default) |

Slack integration is optional -- without tokens, the app still works as a standalone LLM chat.
