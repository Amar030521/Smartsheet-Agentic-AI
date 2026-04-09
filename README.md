# Piramal Smartsheet AI Agent

Production-grade AI agent for Piramal Group's Smartsheet workspaces.
Built on Claude API + Smartsheet REST API + MCP (Model Context Protocol).

---

## Quick Start (Windows)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Smartsheet API token
- Anthropic API key

### 2. Configure
```
cd backend
copy .env.example .env
# Edit .env and add SMARTSHEET_API_TOKEN and ANTHROPIC_API_KEY
```

### 3. Run
Double-click `START.bat`

Or manually:
```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
python main.py

# Terminal 2 — Frontend
cd frontend
npm install
npm start
```

### 4. Open
- **Chat UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

---

## Claude Desktop MCP Integration

To use Smartsheet tools directly inside Claude Desktop:

1. Install Claude Desktop from https://claude.ai/download
2. Open Claude Desktop config:
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
3. Add the MCP server config from `backend/mcp/claude_desktop_config.json`
4. Update the `args` path to your actual install location
5. Restart Claude Desktop
6. You'll see Smartsheet tools available in Claude Desktop's tool panel

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                React Frontend (port 3000)            │
│  - Chat UI with markdown + chart rendering          │
│  - Voice input (Web Speech API)                     │
│  - Session management                               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP /api/v1/chat
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Backend (port 8000)             │
│  - Session store (in-memory / Redis)                │
│  - Request logging + rate limiting                  │
│  - CORS, GZip middleware                            │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              Agent Orchestration Layer               │
│  - Claude API (claude-sonnet-4-5)                   │
│  - Tool-calling loop (max 10 iterations)            │
│  - Multi-turn conversation memory                   │
│  - Chart data extraction                            │
│  - Confirmation flow for destructive actions        │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│            MCP Tool Registry (18 tools)              │
│  Workspaces   Sheets    Rows      Dashboards   SCC  │
│  list         list      create    list         progs │
│  get          get       update    get          bps   │
│               filter    delete    create       rollout│
│               aggregate                       projs  │
│               status                                 │
└──────────────────────┬──────────────────────────────┘
                       │ Smartsheet REST API
┌──────────────────────▼──────────────────────────────┐
│              Smartsheet Workspace                    │
│  PDS Productivity Tracker                           │
│  KPI Tracker                                        │
│  Visa Processing                                    │
│  Control Center Programs                            │
└─────────────────────────────────────────────────────┘
```

---

## MCP Tools (18)

| Tool | Description |
|------|-------------|
| `list_workspaces` | List all workspaces |
| `get_workspace_contents` | Sheets/dashboards/reports in a workspace |
| `list_sheets` | All sheets across account |
| `get_sheet` | Full sheet data with rows + columns |
| `filter_rows` | Filter rows by column conditions |
| `aggregate_column` | Sum/avg/min/max with optional grouping |
| `get_project_status_summary` | Portfolio health: on-track, delayed, at-risk |
| `create_row` | Create a new row |
| `update_row` | Update cells in a row |
| `delete_row` | Delete a row (with confirmation) |
| `list_dashboards` | All dashboards |
| `get_dashboard` | Dashboard details + widgets |
| `create_dashboard` | Create new dashboard |
| `list_scc_programs` | Control Center programs |
| `list_blueprints` | Blueprints in a program |
| `rollout_project` | Roll out project from blueprint |
| `list_scc_projects` | Projects in a program |
| `search_sheets` | Full-text search across account |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SMARTSHEET_API_TOKEN` | ✅ | From Smartsheet → Account → Personal Settings → API Access |
| `ANTHROPIC_API_KEY` | ✅ | From console.anthropic.com |
| `REDIS_URL` | Optional | Redis for persistent sessions (default: in-memory) |
| `REDIS_ENABLED` | Optional | Set `true` to enable Redis |
| `CORS_ORIGINS` | Optional | Comma-separated allowed origins |
| `CLAUDE_MODEL` | Optional | Default: `claude-sonnet-4-5` |
| `RATE_LIMIT_PER_MINUTE` | Optional | Default: 30 requests/min |

---

## Scaling to Production

- Enable Redis (`REDIS_ENABLED=true`) for multi-worker session persistence
- Deploy behind nginx reverse proxy
- Set `APP_ENV=production` for JSON logging
- Use `gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app` for multi-worker
- Teams bot: deploy to Azure Bot Service, point webhook to `/api/v1/chat`
