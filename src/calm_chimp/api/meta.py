from __future__ import annotations

from typing import Dict, List

from .registry import get_api_functions, register_api


@register_api(
    "list_available_tools",
    description="List all deterministic API functions (MCP tools) with descriptions, categories, and parameters.",
    category="meta",
    tags=("tools", "metadata"),
)
def list_available_tools() -> Dict[str, List[dict]]:
    tools = [
        {
            "name": func.name,
            "description": func.description,
            "category": func.category,
            "tags": list(func.tags),
            "parameters": func.parameters,
        }
        for func in sorted(get_api_functions(), key=lambda item: item.name)
    ]
    return {"tools": tools}
