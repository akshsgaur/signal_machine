# Signal — PM Intelligence Platform

## What this is
AI tool that validates PM hypotheses by pulling data from Amplitude, 
Zendesk, Productboard, and Linear via MCP, then synthesizing a 
structured decision brief via 5 parallel agents.

## Stack
- Frontend: Next.js 14 App Router, Tailwind, TypeScript
- Backend: FastAPI, LangGraph, Python 3.11
- DB: Supabase (Postgres)
- AI: openai 4o mini model
- MCP: langchain-mcp-adapters

## Agent architecture
4 research agents run in PARALLEL via asyncio.gather():
- behavioral (Amplitude MCP)
- support (Zendesk/Swifteq MCP)  
- feature (Productboard MCP, self-hosted stdio)
- execution (Linear MCP)

Then 1 synthesis agent reads all 4 outputs sequentially.

## Critical rules
- ALWAYS use return_exceptions=True in asyncio.gather — never fail the whole pipeline
- ALWAYS check the existing file before editing it
- NEVER skip step verification — confirm each build step works before the next
- Agent prompts live in backend/agents/prompts.py — do not inline them

## Current build step
[UPDATE THIS EVERY SESSION]