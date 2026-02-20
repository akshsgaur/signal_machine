"""Explore Linear workspace data via MCP. Run from backend/ with:
   python -m scripts.explore_linear
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from integrations.connections import build_linear_client

LINEAR_KEY = "os.getenv("LINEAR_API_KEY")"


def _dump(label: str, result):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print('='*60)
    try:
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                print(json.dumps(parsed, indent=2)[:3000])
            except Exception:
                print(result[:3000])
        else:
            print(str(result)[:3000])
    except Exception as e:
        print(f"[display error] {e}")


async def call(tools_by_name, name, **kwargs):
    tool = tools_by_name.get(name)
    if not tool:
        print(f"\n[SKIP] {name} — not found")
        return None
    try:
        result = await tool.arun(kwargs)
        _dump(name, result)
        return result
    except Exception as exc:
        print(f"\n[ERROR] {name}: {exc}")
        return None


async def main():
    client = build_linear_client(LINEAR_KEY)
    tools = await client.get_tools()
    by_name = {t.name: t for t in tools}
    print(f"Loaded {len(tools)} tools: {list(by_name.keys())}\n")

    # Teams — foundation for everything else
    await call(by_name, "list_teams")

    # Users in the workspace
    await call(by_name, "list_users")

    # Projects (small first to avoid complexity limit)
    await call(by_name, "list_projects", first=10)

    # Issues — open ones, small batch
    await call(by_name, "list_issues", filter={"state": {"type": {"eq": "started"}}}, first=15)

    # All issues regardless of state (backlog size)
    await call(by_name, "list_issues", first=20)

    # Cycles (sprints)
    await call(by_name, "list_cycles", first=5)

    # Issue labels (hints at product areas)
    await call(by_name, "list_issue_labels", first=30)

    # Issue statuses
    await call(by_name, "list_issue_statuses")

    print("\n\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
