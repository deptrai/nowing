"""Smoke-test nowing_mcp memory tools against a running local backend."""

from __future__ import annotations

import os
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    base_url = os.environ.get("NOWING_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("NOWING_API_KEY")
    if not api_key:
        print(
            "Usage: NOWING_API_KEY=nw_pat_... python mcp_client_smoke.py",
            file=sys.stderr,
        )
        sys.exit(1)

    params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp_server"],
        env={
            "NOWING_BASE_URL": base_url,
            "NOWING_API_KEY": api_key,
            "PATH": os.environ.get("PATH", ""),
        },
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            for tool_name, args in [
                ("nowing_select_workspace", {"workspace": "1"}),
                ("nowing_recall", {"query": "Competitor X"}),
                (
                    "nowing_remember",
                    {
                        "content": "I drink decaf in the morning after walking the dog.",
                        "tags": ["preference", "coffee"],
                    },
                ),
                ("nowing_recall", {"query": "decaf"}),
                (
                    "nowing_update_fact",
                    {
                        "memory_id": 2,
                        "corrected_content": "I drink decaf every morning.",
                        "confidence": 0.99,
                    },
                ),
                ("nowing_recall", {"query": "decaf every morning"}),
                (
                    "nowing_continue_research",
                    {"thread_id": 1, "prompt": "Any updates on competitor X pricing?"},
                ),
            ]:
                result = await session.call_tool(tool_name, args)
                print(f"\n{tool_name}({args}):")
                for content in result.content:
                    text = getattr(content, "text", str(content))
                    print(text)


if __name__ == "__main__":
    anyio.run(main, backend="asyncio")
