# BeamtimeHero

Chat interface for synchrotron beamline users at SSRL BL15-2 and BL4-1 (one repo, one station per deployment -- see [Stations](#stations)). Users ask questions about their experiment through a web UI. Questions are answered by an LLM agent (Claude Code, spawned as a `claude -p --resume` subprocess per turn) that can query beamline scans, search logs, read SPEC state, and generate plots. Conversations are mirrored to Slack where staff can monitor, respond, and collaborate in real time.

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

## Stations

One setting, `BTH_STATION` in `.env`, selects which beamline a deployment serves. The same variable selects the shared `beamtimehero_cli`'s station defaults (counter priority, beam-status PVs, SPEC log naming, hidden tool trees), so both layers switch together.

| | `bl15` (default -- unset) | `bl41` |
|---|---|---|
| Beamline | SSRL BL15-2 (HERFD/XES) | SSRL BL4-1 (wiggler XAS/EXAFS) |
| Station module | `beamline_tools/stations/bl15.py` | `beamline_tools/stations/bl41.py` |
| Agent persona | `.claude/agents/beamline-bth.md` | `.claude/agents/beamline-bth-bl41.md` |
| Runtime allowlist | `agent.settings.json` | `agent.settings.bl41.json` (no `Read` at all) |
| Reference docs | `stations/bl15/context/` | `stations/bl41/context/` |
| Tool profile | 42 tools incl. summary/macro writers | 72 tools: read-only (autonomous_fourone's chat surface + read-only SPEC state, caget, cscan status) plus summary/plan writers |
| SPEC transport | `screen` | `tcp` (SPEC server, localhost:2033) |
| Scan / log dirs | from `.env` | `/fourone`, `/usr/local/lib/spec.log/logfiles` |
| Data / run logs | `./data`, `./logs` | `/fourone/beamtimehero/{data,logs}` |

Each station module holds the env defaults (applied before any upstream import; `.env` wins), the `bth` profile, the refdoc list and the sidebar grouping. Leaving `BTH_STATION` unset reproduces the pre-station BL15-2 behaviour exactly. An unknown station name refuses to start.

The BL4-1 profile is read-only by enumeration except `write-summary` and `save-plan`, which write notes into the user's experiment directory (`BEAMTIMEHERO_PLANS_DIR`, default `{scan_dir}`; `BEAMTIMEHERO_LOG_DIR` when no `YYYY-MM_*` dir resolves): no macro, DB, Slack or SPEC writes, and none of the tools that count (`get-counts` runs `ct`, which drives the cscan box and shutter). `tests/test_bl41_station.py` fails if any other writer or a `mutates` tool reaches it.

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
2. **Permission-time** -- `agent.settings.json` deny rules and the agent frontmatter allowlist (Bash restricted to `beamtimehero bth *` / `ref *`, Read restricted to `stations/bl15/context/**` and `data/**` at BL15-2; no Read at all at BL4-1).

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
  station.py          BTH_STATION -> station module
  stations/bl15.py    BL15-2: bth profile, refdocs, env defaults, sidebar
  stations/bl41.py    BL4-1: the same, read-only profile + note writers
  config.py           Applies the station's env defaults, re-exports upstream config
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
stations/<id>/context/  Beamline reference documents (served via `beamtimehero ref`)
.claude/agents/       Agent personas (beamline-bth = BL15-2, beamline-bth-bl41)
systemd/              beamtimehero.service + install.sh (BL4-1 host)
tests/                pytest suite (CLI gating, profile surface, turn serialization,
                      session recovery)
```

## Setup (Beamline Computer)

### Prerequisites

- Python 3.10+ (the venv on the beamline host runs 3.13)
- The `claude` CLI (Claude Code) on PATH
- Network access to github.com: requirements.txt installs the pinned `slaclab/beamtimehero_cli` commit (`beamtimehero_cli.pin`). To co-develop upstream, `pip install -e ../beamtimehero_cli` afterwards.
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
| `BTH_STATION` | No | `bl15` (default) or `bl41` -- see [Stations](#stations) |
| `LLM_GATEWAY` | No | `stanford`, `slac`, or `default` (default: `default`) |
| `STANFORD_API_KEY` / `SLAC_API_KEY` | For named gateways | API key for the selected gateway |
| `<GW>_API_KEY_PRIMARY` | No | Tried first; `<GW>_API_KEY` is the fallback while it is rate-limited |
| `<GW>_MODEL_ALIAS` | No | Becomes `ANTHROPIC_MODEL` (e.g. `opus`); other `<GW>_*` vars pass through prefix-stripped |
| `CLAUDE_BIN` | No | Path to the `claude` binary (default: `claude` on PATH) |
| `BEAMTIMEHERO_CLAUDE_CONFIG_DIR` | No | `CLAUDE_CONFIG_DIR` for the embedded agent (default: `~/.claude-beamtimehero`), kept apart from the service user's own `~/.claude` |
| `BL_SCAN_DIR` | No | Path to SPEC data root (default: `/data/fifteen`) |
| `BL_LOGS_DIR` | No | Path to SPEC log files |
| `SLACK_BOT_TOKEN` | No | Slack bot token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | No | Slack app-level token (`xapp-...`, for Socket Mode) |
| `SLACK_LLM_CHANNEL_ID` | No | Slack channel for user-LLM conversation log |
| `SLACK_USERS_CHANNEL_ID` | No | Slack channel for staff-user communication |
| `BASE_PATH` | No | URL base path (default: empty, i.e. served at `/`) |
| `PORT` / `HOST` | No | Bind address (defaults: `8080` / `127.0.0.1`; `run.sh` uses `8742`) |
| `BEAMTIMEHERO_DATA_DIR` | No | Data dir for plots + the persisted conversation manifest (station default) |
| `BEAMTIMEHERO_LOG_DIR` / `BEAMTIMEHERO_SUGGESTIONS_DIR` | No | Per-run server logs / user suggestions (station default) |
| `BEAMTIMEHERO_PLANS_DIR` | No | `save-plan` target; `{scan_dir}` expands to the active experiment dir (station default: `logs/plans` at BL15-2, `{scan_dir}` at BL4-1) |
| `BEAMTIMEHERO_TURN_TIMEOUT_SECONDS` | No | Hard wall clock per `claude -p` turn (default: `600`) |
| `BEAMTIMEHERO_FULL_CLI` | No | Operator-only: `1` exposes the full upstream CLI catalog at a terminal |
| `MLFLOW_ENABLED` / `MLFLOW_TRACKING_URI` / `MLFLOW_TRACKING_TOKEN` | No | Best-effort MLflow tracing (disabled by default) |

Slack integration is optional -- without tokens, the app still works as a standalone LLM chat.

## BL4-1 deployment (bl41lx1)

Everything runs as `fourone` (the SPEC data caches and the other apps' files are `fourone`-owned). The repo is group `fourone`, group-writable.

```bash
cd /usr/local/projects/beamtimehero
python3 -m venv venv
HTTPS_PROXY=http://134.79.44.164:3128 venv/bin/pip install -r requirements.txt
cp .env.bl41.example .env && chmod 600 .env     # as fourone; fill in the SLAC keys
mkdir -p /fourone/beamtimehero && chmod 2775 /fourone/beamtimehero
./run.sh                                         # foreground check: http://127.0.0.1:8742/
sudo systemd/install.sh                          # then: service at boot, User=fourone
```

Register the app in `../BL4-1_Web/services.json` (port 8742) so it shows on the launcher.

## Slack setup

One Slack app per beamline (BL4-1 does not share BL15-2's bot). The bridge uses Socket Mode, so no public URL is needed.

1. <https://api.slack.com/apps> → **Create New App** → **From a manifest** → pick the SSRL workspace → paste `slack/manifest.bl41.yml` (YAML tab) → **Create**. This sets Socket Mode, the bot scopes (`chat:write`, `users:read`, `channels:history`, `groups:history`, `im:history`, `im:read`), the bot events (`message.channels`, `message.groups`, `message.im`) and the DM Messages tab.
2. **Basic Information** → *App-Level Tokens* → **Generate Token and Scopes** → name it `socket`, add scope `connections:write` → **Generate** → copy the `xapp-...` token → `SLACK_APP_TOKEN`.
3. **Install App** (or *OAuth & Permissions*) → **Install to Workspace** → allow (a workspace admin may need to approve) → copy the *Bot User OAuth Token* `xoxb-...` → `SLACK_BOT_TOKEN`.
4. Create two channels, e.g. `#beamtimehero-41` (LLM conversation mirror) and `#bl41-users` (staff ↔ user relay), and in each run `/invite @BeamtimeHero 4-1`.
5. Channel IDs: open the channel → click its name at the top → the ID (`C0...`) is at the bottom of the *About* tab → `SLACK_LLM_CHANNEL_ID` and `SLACK_USERS_CHANNEL_ID`.
6. Put the four values in `.env` (as fourone).

Restart the service. The log line `Slack bridge started` (or the error) is in `/fourone/beamtimehero/logs/`.
