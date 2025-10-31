"""Calm Chimp package: desktop AI study planner with MCP integration."""

__all__ = ["main", "run_gui"]


def run_gui() -> None:
    """Launch the PyQt GUI."""
    from .ui import run_gui as _run_gui

    _run_gui()


def main() -> None:
    """Default entry point for `python -m calm_chimp`."""
    run_gui()
