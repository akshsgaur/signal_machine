"""Smoke-test MCP connection layer. Run from backend/ with: python -m scripts.test_mcp"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp.connections import (
    build_amplitude_client,
    build_zendesk_client,
    build_linear_client,
    get_tools_for_client,
)


async def main():
    amp_key = os.getenv("AMPLITUDE_API_KEY", "test-key")
    zen_key = os.getenv("ZENDESK_API_KEY", "test-key")
    lin_key = os.getenv("LINEAR_API_KEY", "test-key")

    print("Testing Amplitude MCP client...")
    amp_client = build_amplitude_client(amp_key)
    amp_tools = await get_tools_for_client(amp_client)
    print(f"  Tools: {[t.name for t in amp_tools]}")

    print("Testing Zendesk MCP client...")
    zen_client = build_zendesk_client(zen_key)
    zen_tools = await get_tools_for_client(zen_client)
    print(f"  Tools: {[t.name for t in zen_tools]}")

    print("Testing Linear MCP client...")
    lin_client = build_linear_client(lin_key)
    lin_tools = await get_tools_for_client(lin_client)
    print(f"  Tools: {[t.name for t in lin_tools]}")

    print("\nMCP connection tests complete (empty tool lists indicate auth/network issue).")


if __name__ == "__main__":
    asyncio.run(main())
