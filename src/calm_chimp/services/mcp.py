from __future__ import annotations

from fastmcp.server import FastMCP
from fastmcp.tools import FunctionTool

from ..api import get_api_functions


def build_mcp_server(host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    tools = []
    for spec in get_api_functions():
        tool = FunctionTool.from_function(
            spec.func,
            name=spec.name,
            description=spec.description,
            tags=set(spec.tags),
        )
        tools.append(tool)
    return FastMCP(
        name="Calm Chimp MCP",
        instructions="Deterministic Supabase calendar tools.",
        tools=tools,
        host=host,
        port=port,
        include_fastmcp_meta=False,
    )


def run_mcp_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = build_mcp_server(host=host, port=port)
    server.run("streamable-http")
