# Signal

Signal is a deep-agent workspace for product teams. It connects product systems, customer insight sources, and engineering context, then turns them into decision-ready briefs and grounded chat answers.

## What It Does

Signal has two primary workflows:

- `Product Chat`: ask questions against connected sources
- `Deep Analysis`: run a multi-step research pipeline that gathers evidence and writes a structured brief

The core design rule is simple:

- the agent should only use sources the user or workspace has actually connected

That means Signal is not just a UI over an LLM. It is a runtime that controls which tools exist for a given user, which evidence is available, and how that evidence is synthesized.

## Current Architecture

### Ghost

Ghost is the primary application database.

It stores:

- user integrations
- workspace integrations
- chat sessions and chat messages
- pipeline runs
- Macroscope run state
- generated analysis metadata

Signal no longer depends on Supabase as its active database backend. The backend uses direct Postgres access through `DATABASE_URL`.

### Airbyte

Airbyte Agent Connectors handle authenticated product-system integrations.

Signal uses Airbyte for:

- provisioning hosted connectors
- storing third-party credentials outside Signal
- reusing connectors per user
- powering runtime access for Airbyte-backed providers that have been fully wired

Currently, `Linear` is the main Airbyte-backed provider wired into runtime. Other Airbyte-backed providers are available for connection management, but may still be connect-only until their runtime path is implemented.

### Macroscope

Macroscope provides workspace-level engineering intelligence.

Signal uses it for:

- engineering chat questions
- deep-analysis engineering research
- code, git history, PR, issue, and delivery context

Macroscope is integrated asynchronously via webhook trigger + callback.

## Deep-Agent Model

The deep analysis pipeline runs in two phases.

### Phase 1: Research

Signal runs only the research agents backed by authenticated sources. Depending on what is connected, this can include:

- behavioral signals
- support signals
- feature demand
- engineering execution
- customer insights
- engineering intelligence via Macroscope

Each research step writes a source file into run storage.

### Phase 2: Synthesis

A synthesis agent reads the evidence files that were actually produced and writes the final decision brief.

This means the brief is grounded in available evidence, not in assumed integrations.

## Runtime Gating

Signal distinguishes between:

- `connected`
- `runtime-ready`

A provider can be connected in the integrations page but still not be usable in chat or deep analysis until its runtime path exists.

This matters because Signal explicitly avoids bluffing tool access. If a source is connected but not runtime-ready, the app should say so rather than pretending it can query it.

## Main Backend Pieces

- [backend/agents/pipeline.py](/Users/akshitgaur/signal/backend/agents/pipeline.py): deep-analysis orchestration
- [backend/agents/prompts.py](/Users/akshitgaur/signal/backend/agents/prompts.py): research + synthesis prompts
- [backend/agents/runtime_plan.py](/Users/akshitgaur/signal/backend/agents/runtime_plan.py): per-user source planning
- [backend/routers/chat.py](/Users/akshitgaur/signal/backend/routers/chat.py): chat routing, tool dispatch, Macroscope chat flow
- [backend/routers/dashboard.py](/Users/akshitgaur/signal/backend/routers/dashboard.py): dashboard data endpoints
- [backend/routers/integrations.py](/Users/akshitgaur/signal/backend/routers/integrations.py): connect/status endpoints
- [backend/integrations/airbyte.py](/Users/akshitgaur/signal/backend/integrations/airbyte.py): Airbyte connect lifecycle
- [backend/integrations/airbyte_runtime.py](/Users/akshitgaur/signal/backend/integrations/airbyte_runtime.py): hosted Airbyte runtime adapters
- [backend/integrations/macroscope.py](/Users/akshitgaur/signal/backend/integrations/macroscope.py): Macroscope trigger logic
- [backend/routers/macroscope.py](/Users/akshitgaur/signal/backend/routers/macroscope.py): Macroscope callback endpoint
- [backend/db/supabase.py](/Users/akshitgaur/signal/backend/db/supabase.py): Ghost/Postgres data access layer

## Frontend

The frontend is a Next.js app with:

- `/connect` for integrations
- `/` for the main workspace UI
- dashboard, chat, and insights surfaces

Relevant files:

- [frontend/app/connect/page.tsx](/Users/akshitgaur/signal/frontend/app/connect/page.tsx)
- [frontend/app/app/page.tsx](/Users/akshitgaur/signal/frontend/app/app/page.tsx)
- [frontend/components/IntegrationCard.tsx](/Users/akshitgaur/signal/frontend/components/IntegrationCard.tsx)
- [frontend/lib/api.ts](/Users/akshitgaur/signal/frontend/lib/api.ts)

## Local Setup

### Backend env

Set at minimum:

```env
DATABASE_URL=postgresql://...
OPENAI_API_KEY=...
AIRBYTE_CLIENT_ID=...
AIRBYTE_CLIENT_SECRET=...
AIRBYTE_ORGANIZATION_ID=...
BACKEND_PUBLIC_URL=https://your-public-backend-url
MACROSCOPE_CALLBACK_TOKEN=optional
```

### Backend

```bash
cd backend
source signal/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Ghost Queries

Useful examples:

```bash
ghost sql g3lhadalmx "select tablename from pg_tables where schemaname='public' order by tablename;"
ghost sql g3lhadalmx "select * from user_integrations limit 20;"
ghost sql g3lhadalmx "select * from workspace_integrations limit 20;"
ghost sql g3lhadalmx "select id, status, created_at from pipeline_runs order by created_at desc limit 10;"
ghost sql g3lhadalmx "select id, mode, workflow_id, status, completed_at from macroscope_runs order by created_at desc limit 10;"
```

## Current Notes

- `Linear` is connected through Airbyte and now wired into runtime through the hosted connector path.
- `Macroscope` is workspace-scoped and used for engineering context in chat and deep analysis.
- Some Airbyte-backed providers are still connect-only until their runtime execution path is added.

## Stack

- Next.js
- React
- TypeScript
- FastAPI
- Python
- Ghost / Postgres
- Airbyte Agent Connectors
- Macroscope
- LangChain
- LangGraph
- Clerk
- OpenAI models
- HTTPX
- ngrok
