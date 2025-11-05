"""Public API surface for MCP and the GUI."""

from __future__ import annotations

from .registry import ApiFunction, call_api, get_api_functions, register_api
from .state import api_state

# Import endpoints so decorators run at module import time.
from . import endpoints  # noqa: F401

__all__ = ["ApiFunction", "api_state", "call_api", "get_api_functions", "register_api"]
