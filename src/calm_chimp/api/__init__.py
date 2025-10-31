"""Deterministic local API surface powering MCP tools and the GUI."""

from .registry import API_REGISTRY, ApiFunction, call_api, get_api_functions, register_api

# Import submodules to ensure API functions are registered on package import.
from . import calendar, history, planning, subjects, tasks  # noqa: F401

__all__ = [
    "API_REGISTRY",
    "ApiFunction",
    "call_api",
    "get_api_functions",
    "register_api",
]
