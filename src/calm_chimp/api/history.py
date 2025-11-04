from __future__ import annotations

from typing import Dict, List

from ..core import HistoryEntry, SupabaseDatabase
from .registry import register_api

database = SupabaseDatabase()


def _serialize(entry: HistoryEntry) -> dict:
    return entry.to_dict()


@register_api(
    "list_history_entries",
    description="List all history entries in chronological order.",
    category="history",
    tags=("history", "list"),
)
def list_history_entries() -> Dict[str, List[dict]]:
    entries = sorted(database.list_history(), key=lambda entry: entry.timestamp)
    return {"entries": [_serialize(entry) for entry in entries]}


@register_api(
    "get_history_entry_details",
    description="Get details for a specific history entry by ID.",
    category="history",
    tags=("history", "get"),
)
def get_history_entry_details(history_id: str) -> Dict[str, object]:
    for entry in database.list_history():
        if entry.id == history_id:
            return {"entry": _serialize(entry)}
    return {"entry": None}


@register_api(
    "revert_calendar_to_history_entry",
    description="Revert tasks and subjects to a previous history snapshot.",
    category="history",
    tags=("history", "revert"),
)
def revert_calendar_to_history_entry(history_id: str) -> Dict[str, object]:
    entry = database.revert_to_history(history_id)
    return {"restored_entry": _serialize(entry) if entry else None}


@register_api(
    "list_recent_history_actions",
    description="List the ten most recent history actions.",
    category="history",
    tags=("history", "recent"),
)
def list_recent_history_actions() -> Dict[str, List[dict]]:
    entries = database.list_history()[-10:]
    return {"entries": [_serialize(entry) for entry in entries]}
