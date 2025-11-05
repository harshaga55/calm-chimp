"""Calm Chimp application package."""

from __future__ import annotations

from .ui.app import run_gui as run_gui

__all__ = ["run_gui"]


def main() -> None:
    run_gui()
