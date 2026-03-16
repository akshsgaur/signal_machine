# Signal — PM Intelligence Platform

Signal validates product hypotheses by pulling live data from your tools and synthesizing a structured decision brief with parallel AI agents. Instead of gut feelings, you get a multi-source evidence report in minutes.

---

## How It Works

You write a hypothesis. Signal runs 4 research agents in parallel against your connected data sources, then a 5th synthesis agent reads all 4 outputs and writes a decision brief.

```
Hypothesis: "Users who complete onboarding in under 5 min have 2× 30-day retention"

  ┌─────────────────────────────────────────────────────────────┐
  │                    Phase 1  (parallel)                       │
  │                                                             │
  │  Amplitude ──► behavioral-agent ──► amplitude_signals.md   │
  │  Zendesk   ──► support-agent    ──► zendesk_signals.md     │
  │  Productboard► feature-agent    ──► feature_intelligence.md │
  │  Linear    ──► execution-agent  ──► execution_reality.md   │
  └─────────────────────────────────────────────────────────────┘
                            │
                            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                    Phase 2  (sequential)                     │
  │                                                             │
  │  synthesis-agent  reads all 4 files                        │
  │       └──► output/decision_brief.md                        │
  └─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              Decision: Pursue / Deprioritize /
                        Investigate Further / Pivot
```

The frontend streams agent completions via SSE so you watch the pipeline run in real time.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, react-markdown |
| Backend | FastAPI 0.115, Python 3.11, uvicorn |
| Agents | LangGraph 0.2.74, LangChain 1.0 (`create_agent`) |
| Model | GPT-4o mini (`gpt-4o-mini`) via langchain-openai |
| MCP | langchain-mcp-adapters, MultiServerMCPClient |
| Database | Supabase (Postgres) |
| Streaming | Server-Sent Events (SSE), disk-poll architecture |

---

## Data Sources

| Integration | What it contributes | Transport |
|---|---|---|
| **Amplitude** | Behavioral analytics — funnels, retention, cohorts, event data | MCP over HTTP |
| **Zendesk** (via Swifteq) | Support tickets — themes, pain points, verbatim quotes | MCP over HTTP |
| **Productboard** | Feature requests — demand signals, user segment breakdown | MCP over stdio |
| **Linear** | Engineering backlog — WIP, blockers, team velocity | MCP over HTTP |

Integrations are optional. If one is not connected, the agent writes a fallback note and the brief reflects reduced confidence for that source.

### Chat Integrations Catalog

The integrations page is backend-driven and groups providers by category. In this phase:

- Fully wired for connect + chat: `Aha!`, `Amplitude`, `Atlassian Jira + Confluence`, `monday.com`, `Productboard`, `Tableau`, plus the existing `Slack` integration path.
- Deferred as catalog-only entries: `Notion`, `Miro`, `Figma`.
- Shown as blocked for this phase: `Gong`, `SurveyMonkey`, `Loom`, `Gartner`.

The hypothesis-analysis pipeline remains limited to the existing pipeline sources; new providers are chat-first.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project
- An [Anthropic API key](https://console.anthropic.com)
- API tokens for whichever integrations you want to connect

---

## Setup

### 1. Supabase Schema

Run this once in your Supabase SQL editor:

```sql
create table user_integrations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  integration_type text not null,
  oauth_token text,
  credentials_json jsonb,
  connected_at timestamptz default now(),
  last_used_at timestamptz,
  unique(user_id, integration_type)
);

create table pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  hypothesis text not null,
  product_area text,
  status text default 'running',
  brief text,
  created_at timestamptz default now(),
  completed_at timestamptz
);

alter table user_integrations enable row level security;
alter table pipeline_runs enable row level security;
create policy "allow all" on user_integrations for all using (true);
create policy "allow all" on pipeline_runs for all using (true);
```

### 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY
```

**`backend/.env`**
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
OPENAI_API_KEY=sk-...
# Optional:
PRODUCTBOARD_SIDECAR_PATH=/path/to/productboard-mcp/index.js
AHA_MCP_COMMAND=uvx mcp-aha
MONDAY_MCP_COMMAND=uvx monday-mcp
TABLEAU_MCP_COMMAND=uvx tableau-mcp
```

> Use the **service role** key for `SUPABASE_KEY` (backend only, never exposed to the browser).
> For stdio-backed providers you can set either `*_MCP_COMMAND` or `*_MCP_SERVER_PATH` depending on how the MCP server is installed.

### 3. Frontend

```bash
cd frontend
npm install

cp .env.local.example .env.local
# Edit .env.local — fill in NEXT_PUBLIC_* values
```

**`frontend/.env.local`**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

> Use the **anon** key for `NEXT_PUBLIC_SUPABASE_ANON_KEY` (browser-safe).

---

## Running Locally

```bash
# Terminal 1 — backend (run from the backend/ directory)
cd backend
source venv/bin/activate
uvicorn main:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs

# Terminal 2 — frontend
cd frontend
npm run dev
# UI available at http://localhost:3000
```

---

## Usage

1. **Connect integrations** — go to `http://localhost:3000/connect` and paste API tokens for the tools you use. Each token is stored encrypted in Supabase. You can connect any subset; unconnected sources are gracefully skipped.

2. **Submit a hypothesis** — go to `http://localhost:3000`, write your hypothesis and the product area it applies to, then click **Analyze**.

3. **Watch the pipeline** — you're redirected to the run page. The left panel shows each agent completing in real time. The decision brief appears on the right when the synthesis agent finishes.

### Example hypotheses

- *"Users who invite a teammate within 24 hours of signup have 3× 90-day retention"*
- *"The checkout drop-off is driven by mandatory account creation, not payment friction"*
- *"Power users want bulk export — this is blocking enterprise deals"*
- *"The mobile onboarding flow has lower completion than desktop because of the file upload step"*

---

## API Reference

| Method | Path | Body / Params | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{"status": "ok"}` |
| `GET` | `/integrations/catalog` | — | grouped integration metadata for the connect page |
| `POST` | `/integrations/connect` | `{user_id, integration_type, credentials}` or legacy `{token}` | `{"status": "connected"}` |
| `GET` | `/integrations/{user_id}` | — | `{"amplitude": {"connected": true, ...}, ...}` |
| `POST` | `/run` | `{user_id, hypothesis, product_area}` | `{"run_id": "<uuid>"}` |
| `GET` | `/run/{run_id}/stream` | — | SSE stream |

### SSE Events (`/run/{run_id}/stream`)

```jsonc
// Fired when each research agent writes its output file
{ "type": "agent_update", "agent": "behavioral", "status": "complete" }

// Fired when the synthesis agent writes the decision brief
{ "type": "brief_chunk", "content": "# Decision Brief\n..." }

// Terminal event — closes the stream
{ "type": "status", "status": "complete" }  // or "failed" | "timeout"
```

---

## Architecture Details

### Deep Agent State

All agents share a `DeepAgentState` that extends LangGraph's `AgentState`:

```python
class DeepAgentState(AgentState):
    todos: list[Todo]          # planning layer (write_todos / read_todos)
    files: dict[str, str]      # virtual filesystem (ls / read_file / write_file)
    run_id: str                # disk mirror key
```

The `files` dict is the **shared memory** between agents. Research agents write to it; the synthesis agent reads from it. Every `write_file` call also mirrors to `backend/storage/files/{run_id}/` on disk — the SSE router polls disk existence to detect agent completion without reading LangGraph state.

### MCP Connections

MCP clients are created fresh per pipeline run inside `run_signal_pipeline()`, not at module import time. This is because API tokens are only available after fetching from Supabase at request time.

```python
# Per-run client creation (connections.py)
build_amplitude_client(token)    # streamable_http → https://mcp.amplitude.com/mcp
build_zendesk_client(token)      # streamable_http → https://agenthelper.swifteq.com/mcp
build_linear_client(token)       # streamable_http → https://mcp.linear.app/mcp
build_productboard_client(token) # stdio → node $PRODUCTBOARD_SIDECAR_PATH
```

`get_tools_for_client()` wraps tool discovery in try/except — a failed MCP connection returns `[]` tools rather than crashing the pipeline.

### Fault Isolation

`_run_agent()` (the function submitted to `ThreadPoolExecutor`) **never raises**. On any exception it writes a `{name}/error.md` fallback file and returns it as output. The synthesis agent will still run and note the missing source in the brief. `asyncio.gather()` for MCP tool discovery always uses `return_exceptions=True` for the same reason.

---

## Project Structure

```
signal/
├── CLAUDE.md                   ← rules for Claude Code (read before editing)
├── AGENT.md                    ← reference for all AI coding agents
├── README.md                   ← this file
│
├── backend/
│   ├── main.py                 ← FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example
│   │
│   ├── agents/
│   │   ├── state.py            ← DeepAgentState, reducers, Todo
│   │   ├── prompts.py          ← all prompt strings (never inline elsewhere)
│   │   ├── pipeline.py         ← run_signal_pipeline(), AGENT_FILE_MAP
│   │   ├── file_tools.py       ← ls, read_file, write_file, write_file_to_storage
│   │   ├── todo_tools.py       ← write_todos, read_todos
│   │   ├── think_tool.py       ← reflection tool (called after each MCP tool call)
│   │   └── subagents.py        ← create_subagent_agents() factory
│   │
│   ├── mcp/
│   │   └── connections.py      ← MCP client builders + get_tools_for_client()
│   │
│   ├── db/
│   │   └── supabase.py         ← token CRUD + pipeline run CRUD
│   │
│   ├── routers/
│   │   ├── integrations.py     ← /integrations endpoints
│   │   └── pipeline.py         ← /run endpoints + SSE
│   │
│   └── scripts/
│       ├── test_db.py
│       ├── test_mcp.py
│       └── test_pipeline.py
│
└── frontend/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx             ← hypothesis form (Screen 2)
    │   ├── connect/page.tsx     ← integrations (Screen 1)
    │   └── run/[id]/page.tsx   ← live run view (Screen 3)
    │
    ├── components/
    │   ├── HypothesisForm.tsx
    │   ├── PipelineTracker.tsx
    │   ├── DecisionBrief.tsx
    │   └── IntegrationCard.tsx
    │
    └── lib/
        ├── api.ts              ← backend API calls
        ├── supabase.ts         ← Supabase browser client
        └── useSSE.ts           ← EventSource hook
```

---

## Extending Signal

### Adding a new data source

1. Add a prompt constant to `backend/agents/prompts.py`
2. Add a client builder to `backend/mcp/connections.py`
3. Add the agent to `research_agents` dict in `run_signal_pipeline()` (`pipeline.py`)
4. Add its `{key: file_path}` entry to `AGENT_FILE_MAP` in `pipeline.py`
5. Add a label to `AGENT_LABELS` in `frontend/components/PipelineTracker.tsx`
6. Add an entry to `INTEGRATIONS` in `frontend/app/connect/page.tsx`

### Changing the AI model

The model is set in `run_signal_pipeline()`:

```python
model = init_chat_model(model="gpt-4o-mini", temperature=0.0)
```

`init_chat_model` supports any LangChain-compatible provider — swap `"gpt-4o-mini"` for `"anthropic:claude-sonnet-4-6"`, `"google_genai:gemini-2.0-flash"`, etc. and install the corresponding package.

### Smoke testing

```bash
cd backend
source venv/bin/activate

python -m scripts.test_db        # Supabase read/write
python -m scripts.test_mcp       # MCP client instantiation + tool listing
python -m scripts.test_pipeline  # full end-to-end run (uses real LLM + Supabase)
```

---

## Design Decisions

| Decision | Why |
|---|---|
| `ThreadPoolExecutor` for Phase 1 | `agent.invoke()` is synchronous; threads let 4 agents run concurrently without async complexity inside the agents themselves |
| Disk-poll SSE instead of LangGraph state SSE | Simple and decoupled — SSE router checks for file existence on disk; no need to read or subscribe to LangGraph internals |
| MCP clients created per run | Tokens are fetched from DB at request time; no caching means no token leakage across users |
| Virtual filesystem as shared memory | Research agents write files; synthesis reads them — no direct agent-to-agent calls, no shared mutable state, no race conditions |
| All prompts in `prompts.py` | Single source of truth for agent behavior; easier to iterate on prompts without touching orchestration code |
| `return_exceptions=True` everywhere | A single failed integration should never abort the whole pipeline |

---

## Contributing

The codebase follows the rules in `CLAUDE.md`. Before editing:

- Read `AGENT.md` for the full architecture reference
- Never inline prompt strings — add them to `backend/agents/prompts.py`
- Never let `_run_agent` raise — it is the fault isolation boundary for Phase 1
- `AGENT_FILE_MAP` in `pipeline.py` is the canonical mapping of agent → output file; keep it in sync
