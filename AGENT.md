# Signal — Agent Reference

This file is the authoritative reference for AI coding agents (Claude Code, Cursor, Windsurf, etc.)
working on the Signal codebase. Read this before touching any file.

---

## What Signal Does

Signal validates PM hypotheses by pulling live data from 4 SaaS tools via MCP, running 4 parallel
research agents, then synthesizing a structured decision brief with a 5th agent. The output is a
markdown brief that tells a PM whether to pursue, deprioritize, or investigate their hypothesis.

**Entry point for a run:** `POST /run` → background task → `run_signal_pipeline()` → SSE stream

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 App Router, TypeScript, Tailwind CSS |
| Backend | FastAPI 0.115, Python 3.11, uvicorn |
| Agents | LangGraph 0.2.74, LangChain 1.0, `langchain.agents.create_agent` |
| MCP | `langchain-mcp-adapters`, `MultiServerMCPClient` |
| AI model | `claude-sonnet-4-6` via `langchain-anthropic` |
| Database | Supabase (Postgres), `supabase-py` 2.7 |
| Storage | Local disk at `backend/storage/files/{run_id}/` |

---

## Repository Layout

```
signal/
├── CLAUDE.md                          ← project rules for Claude Code (read first)
├── AGENT.md                           ← this file
├── backend/
│   ├── main.py                        ← FastAPI app, CORS, router registration
│   ├── requirements.txt
│   ├── .env                           ← gitignored; copy from .env.example
│   ├── storage/files/                 ← gitignored; agent disk output per run_id
│   ├── agents/
│   │   ├── state.py                   ← DeepAgentState, file_reducer, todo_reducer, Todo
│   │   ├── prompts.py                 ← ALL prompt strings (never inline elsewhere)
│   │   ├── file_tools.py              ← ls, read_file, write_file, write_file_to_storage
│   │   ├── todo_tools.py              ← write_todos, read_todos
│   │   ├── think_tool.py              ← think_tool (reflection after MCP calls)
│   │   ├── subagents.py               ← create_subagent_agents() factory
│   │   └── pipeline.py               ← run_signal_pipeline(), _run_agent(), AGENT_FILE_MAP
│   ├── mcp/
│   │   └── connections.py             ← build_*_client(), get_tools_for_client()
│   ├── db/
│   │   └── supabase.py                ← token CRUD, pipeline run CRUD
│   ├── routers/
│   │   ├── integrations.py            ← POST /integrations/connect, GET /integrations/{user_id}
│   │   └── pipeline.py               ← POST /run, GET /run/{run_id}/stream (SSE)
│   └── scripts/
│       ├── test_db.py                 ← smoke test Supabase layer
│       ├── test_mcp.py                ← smoke test MCP connections
│       └── test_pipeline.py          ← end-to-end pipeline test
└── frontend/
    ├── app/
    │   ├── layout.tsx                 ← Inter font, bg-[#0A0A0A], global styles
    │   ├── page.tsx                   ← Screen 2: HypothesisForm
    │   ├── connect/page.tsx           ← Screen 1: IntegrationCard × 4
    │   └── run/[id]/page.tsx          ← Screen 3: PipelineTracker + DecisionBrief
    ├── components/
    │   ├── HypothesisForm.tsx         ← textarea + product area + submit → POST /run
    │   ├── PipelineTracker.tsx        ← 5 rows (4 agents + synthesis), spinner → checkmark
    │   ├── DecisionBrief.tsx          ← react-markdown + skeleton while loading
    │   └── IntegrationCard.tsx        ← token input + Connect button, green check when done
    └── lib/
        ├── api.ts                     ← startRun(), connectIntegration(), getIntegrations()
        ├── supabase.ts                ← supabase client (anon key, browser-safe)
        └── useSSE.ts                  ← EventSource hook → agentStatuses, brief, pipelineStatus
```

---

## Agent Architecture

### DeepAgentState (`backend/agents/state.py`)

Every agent in Signal shares this state schema:

```python
class DeepAgentState(AgentState):
    todos: Annotated[NotRequired[list[Todo]], todo_reducer]   # planning layer
    files: Annotated[NotRequired[dict[str, str]], file_reducer]  # virtual filesystem
    run_id: NotRequired[str]                                  # disk mirror key
```

- `files` is the **shared memory** between agents — research agents write to it, synthesis reads from it.
- `file_reducer` merges dicts (right side wins on conflict). Never replace; always merge.
- `todo_reducer` replaces the whole list (most recent wins — tools send the full list every time).

### Virtual Filesystem

Agents communicate exclusively through the virtual filesystem (`state["files"]`). Every `write_file`
call also mirrors content to disk at `backend/storage/files/{run_id}/{file_path}`.

| Tool | What it does |
|---|---|
| `ls(state)` | Lists all keys in `state["files"]` |
| `read_file(file_path, state)` | Reads from `state["files"][file_path]` with line numbers |
| `write_file(file_path, content, state, tool_call_id)` | Writes to state + mirrors to disk; returns `Command` |
| `write_file_to_storage(run_id, file_path, content)` | Disk-only write (used in error fallbacks) |

Path traversal is blocked by `_safe_path()` — paths must stay inside `storage/files/{run_id}/`.

### Pipeline Flow (`backend/agents/pipeline.py`)

```
run_signal_pipeline(run_id, user_id, hypothesis, product_area)
  │
  ├── 1. get_all_tokens(user_id)                     # Supabase → {integration: token}
  ├── 2. asyncio.gather(get_tools_for_client × 4)    # MCP tool discovery, return_exceptions=True
  ├── 3. init_chat_model("anthropic:claude-sonnet-4-6")
  │
  ├── Phase 1: ThreadPoolExecutor(max_workers=4)
  │   ├── _run_agent("behavioral", ...) → behavioral/amplitude_signals.md
  │   ├── _run_agent("support", ...)    → support/zendesk_signals.md
  │   ├── _run_agent("feature", ...)    → productboard/feature_intelligence.md
  │   └── _run_agent("execution", ...) → linear/execution_reality.md
  │
  ├── Phase 2: synthesis_agent.invoke(files=<all 4 files>)
  │   └── reads all 4 files → writes output/decision_brief.md
  │
  └── update_pipeline_brief(run_id, brief, "complete")  # Supabase
```

**`_run_agent` never raises.** On any exception it writes `{name}/error.md` and returns that.
This is the fault-isolation guarantee of Phase 1.

**`asyncio.gather` always uses `return_exceptions=True`** for MCP tool discovery.
Collapsed to `[]` afterwards if exception — agent still runs, just has no MCP tools.

### Agent Roster

| Agent key | Prompt constant | MCP source | Output file |
|---|---|---|---|
| `behavioral` | `BEHAVIORAL_AGENT_PROMPT` | Amplitude | `behavioral/amplitude_signals.md` |
| `support` | `SUPPORT_AGENT_PROMPT` | Zendesk (Swifteq) | `support/zendesk_signals.md` |
| `feature` | `FEATURE_AGENT_PROMPT` | Productboard | `productboard/feature_intelligence.md` |
| `execution` | `EXECUTION_AGENT_PROMPT` | Linear | `linear/execution_reality.md` |
| `synthesis` | `SYNTHESIS_AGENT_PROMPT` | none (reads files) | `output/decision_brief.md` |

`AGENT_FILE_MAP` in `pipeline.py` is the canonical mapping used by both the pipeline and the SSE
router to detect file creation. If you add an agent, update this dict.

### Tool set per agent

```
base_tools = [ls, read_file, write_file, think_tool]   # all agents
research agent = base_tools + mcp_tools                # mcp_tools may be [] if integration missing
synthesis agent = base_tools                           # no MCP — reads virtual filesystem only
```

### think_tool

Every research agent prompt instructs it to call `think_tool` after **each** MCP tool call.
This is a pure reflection hook — it returns immediately with no side effects and helps the model
plan its next step. Do not remove it from the base tool list.

---

## MCP Connections (`backend/mcp/connections.py`)

MCP clients are **created per pipeline run** inside `run_signal_pipeline`. They are never
instantiated at module import time because tokens are only available at runtime.

| Integration | Transport | URL / Command |
|---|---|---|
| Amplitude | `streamable_http` | `https://mcp.amplitude.com/mcp` |
| Zendesk | `streamable_http` | `https://agenthelper.swifteq.com/mcp` |
| Linear | `streamable_http` | `https://mcp.linear.app/mcp` |
| Productboard | `stdio` | `node $PRODUCTBOARD_SIDECAR_PATH` |

All clients use `Authorization: Bearer {token}` headers (or env var for Productboard stdio).
`get_tools_for_client()` wraps `client.get_tools()` in try/except and returns `[]` on any failure.
An agent with an empty MCP tool list still runs — it will write a `MISSING_SOURCE_NOTE` fallback.

---

## Database (`backend/db/supabase.py`)

### Tables

**`user_integrations`**
```
id              uuid PK
user_id         text
integration_type text   ('amplitude' | 'zendesk' | 'linear' | 'productboard')
oauth_token     text
connected_at    timestamptz
last_used_at    timestamptz
UNIQUE(user_id, integration_type)
```

**`pipeline_runs`**
```
id           uuid PK
user_id      text
hypothesis   text
product_area text
status       text   ('running' | 'complete' | 'failed')
brief        text   (populated on completion — full markdown)
created_at   timestamptz
completed_at timestamptz
```

No `agent_outputs` JSONB — agent outputs live in the virtual filesystem on disk.

### Key functions

```python
store_integration_token(user_id, integration_type, token)   # upsert
get_integration_token(user_id, integration_type) -> str | None
get_all_tokens(user_id) -> dict[str, str]                   # {type: token}
create_pipeline_run(user_id, hypothesis, product_area) -> str  # UUID
update_pipeline_brief(run_id, brief, status)                # writes brief + completed_at
get_pipeline_run(run_id) -> dict
```

The Supabase client is a module-level singleton initialized lazily in `_get_client()`.
It reads `SUPABASE_URL` and `SUPABASE_KEY` from the environment.

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/integrations/connect` | Store API token `{user_id, integration_type, token}` |
| `GET` | `/integrations/{user_id}` | List connected integrations (booleans, no tokens) |
| `POST` | `/run` | Start pipeline run `{user_id, hypothesis, product_area}` → `{run_id}` |
| `GET` | `/run/{run_id}/stream` | SSE stream of pipeline events |

### SSE Event Schema (`/run/{run_id}/stream`)

The stream polls disk every 1 second for up to 5 minutes.

```json
{ "type": "agent_update", "agent": "behavioral", "status": "complete" }
{ "type": "brief_chunk",  "content": "# Decision Brief\n..." }
{ "type": "status",       "status": "complete" }  // or "failed" | "timeout"
```

Frontend consumes this in `lib/useSSE.ts`. The `status` event triggers `EventSource.close()`.

---

## Prompts (`backend/agents/prompts.py`)

**All prompt strings must live in `prompts.py`.** Never inline prompt text into agent files,
pipeline files, or any other module. This is a hard rule from `CLAUDE.md`.

Constants defined:
- `BEHAVIORAL_AGENT_PROMPT` — template vars: `{hypothesis}`, `{product_area}`
- `SUPPORT_AGENT_PROMPT` — same template vars
- `FEATURE_AGENT_PROMPT` — same template vars
- `EXECUTION_AGENT_PROMPT` — same template vars
- `SYNTHESIS_AGENT_PROMPT` — same template vars (reads files, no MCP)
- `MISSING_SOURCE_NOTE` — template var: `{source}` (used when integration unavailable)
- `TODO_USAGE_INSTRUCTIONS` — injected into agent system prompts
- `FILE_USAGE_INSTRUCTIONS` — injected into agent system prompts
- `WRITE_TODOS_DESCRIPTION` — tool description for `write_todos`

Each research prompt ends with `STOP after writing the file.` — this is intentional and
prevents agents from looping after completing their single output.

---

## Environment Variables

### Backend (`backend/.env`)
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key          # service role, not anon
ANTHROPIC_API_KEY=your-anthropic-key
PRODUCTBOARD_SIDECAR_PATH=/path/to/index.js  # optional, defaults to /opt/productboard-mcp/index.js
FILES_STORAGE_ROOT=/custom/path              # optional, overrides default storage/files/
```

### Frontend (`frontend/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key  # anon key, safe for browser
```

---

## Running Locally

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in values
uvicorn main:app --reload     # starts on :8000
```

Run from the `backend/` directory so relative paths for `storage/files/` resolve correctly.

### Frontend
```bash
cd frontend
cp .env.local.example .env.local   # fill in values
npm install
npm run dev                         # starts on :3000
```

### Smoke tests (run from `backend/`)
```bash
python -m scripts.test_db       # tests Supabase CRUD
python -m scripts.test_mcp      # tests MCP client instantiation
python -m scripts.test_pipeline # end-to-end pipeline (needs .env)
```

---

## Supabase Schema (run once in SQL editor)

```sql
create table user_integrations (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  integration_type text not null,
  oauth_token text not null,
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

---

## Critical Rules for Agents

1. **Never inline prompts.** All prompt strings belong in `backend/agents/prompts.py`.

2. **`asyncio.gather` must use `return_exceptions=True`** when calling MCP or any async operation
   that could fail independently. Never let one integration failure kill the whole pipeline.

3. **`_run_agent` must never raise.** It catches all exceptions and writes a fallback file.
   This is the fault isolation boundary for Phase 1.

4. **MCP clients are created inside `run_signal_pipeline`, not at module level.** Tokens are
   only available at request time. Never cache a client across pipeline runs.

5. **`write_file` returns a `Command`.** It uses `InjectedState` + `InjectedToolCallId` — the
   LangGraph `ToolNode` handles calling convention. Do not call it like a regular function.

6. **`AGENT_FILE_MAP` is the source of truth** for which file path each agent writes.
   The SSE router and the pipeline both import it from `pipeline.py`. If you add an agent,
   add its entry to this dict.

7. **Storage path resolution:** `_storage_root()` checks `FILES_STORAGE_ROOT` env var first,
   then defaults to `{backend_root}/storage/files/`. Always run uvicorn from `backend/`.

8. **`recursion_limit: 50`** is set on all agent invocations. Do not raise it above 100 without
   justification — runaway loops will exhaust the context window.

9. **No `agent_outputs` table.** Agent data lives on disk. Supabase only stores the final brief
   string and run metadata. Do not add JSONB agent output storage.

10. **Frontend user_id is hardcoded** to `"demo-user-001"` in `HypothesisForm.tsx` and
    `connect/page.tsx`. Auth is not yet implemented — replace both when adding auth.

---

## Key Design Patterns

### Adding a new research agent

1. Add prompt constant to `backend/agents/prompts.py`.
2. Add a new MCP client builder to `backend/mcp/connections.py` if a new integration.
3. Add the agent to the `research_agents` dict in `run_signal_pipeline()` in `pipeline.py`.
4. Add its `{key: file_path}` entry to `AGENT_FILE_MAP`.
5. Add a row to `PipelineTracker.tsx` (`AGENT_LABELS` dict) in the frontend.
6. Add an `IntegrationCard` to `frontend/app/connect/page.tsx` (`INTEGRATIONS` array).

### Adding a new API endpoint

Add a route to the appropriate router in `backend/routers/`. Register new routers in `main.py`
with `app.include_router(...)`. Mirror any new data shape to `frontend/lib/api.ts`.

### Modifying agent behavior

Change the relevant prompt in `prompts.py` only. Do not change how `create_agent` is called
or which base tools are passed — the tool set is intentionally minimal.

---

## Frontend Component Map

| Component | Screen | Responsibility |
|---|---|---|
| `app/page.tsx` | Home | Renders `HypothesisForm`, link to `/connect` |
| `app/connect/page.tsx` | Integrations | 4 `IntegrationCard` components, polls `/integrations/{user_id}` |
| `app/run/[id]/page.tsx` | Run | Calls `useSSE`, renders `PipelineTracker` + `DecisionBrief` |
| `HypothesisForm` | Home | Form → `startRun()` → `router.push('/run/{id}')` |
| `PipelineTracker` | Run | 5 agent rows, spinner → checkmark, elapsed timer via `setInterval` |
| `DecisionBrief` | Run | `react-markdown` + `remark-gfm`, skeleton while loading |
| `IntegrationCard` | Integrations | Password input → `connectIntegration()`, green indicator when connected |
| `useSSE` | Run | `EventSource` → `{ agentStatuses, brief, pipelineStatus }` |

---

## Origin

The Deep Agent pattern (DeepAgentState, virtual filesystem, todo tools) is adapted from
`/Users/akshitgaur/aidium.ai/backend/agents/`. The aidium primitives were adapted for Signal's
specific 2-phase (parallel research + sequential synthesis) structure. Do not copy aidium files
directly — always adapt to Signal's module layout and naming conventions.
