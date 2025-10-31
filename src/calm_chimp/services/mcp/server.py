from __future__ import annotations

from fastmcp import FastMCP

from ...api import get_api_functions

INSTRUCTIONS = (
    "Calm Chimp MCP server exposes deterministic calendar and study planning tools. "
    "Use the tools to add, schedule, review, and revert studying tasks directly from chat."
)

server = FastMCP(
    name="calm-chimp",
    instructions=INSTRUCTIONS,
    website_url="https://example.com/calm-chimp",
)

# Dynamically register all API functions as MCP tools.
for api_function in get_api_functions():
    server.tool(
        api_function.func,
        name=api_function.name,
        description=api_function.description,
        tags=set(api_function.tags),
    )


def run_mcp_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    import asyncio

    asyncio.run(server.run_streamable_http_async(host=host, port=port))
