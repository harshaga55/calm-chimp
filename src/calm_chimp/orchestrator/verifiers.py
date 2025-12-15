from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "summary": self.summary}


def verify_tool_output(tool_name: str, output: Optional[Dict[str, Any]]) -> VerificationResult:
    if output is None:
        return VerificationResult(False, "No output returned.")
    if not isinstance(output, dict):
        return VerificationResult(False, "Output is not a mapping.")

    if tool_name == "refresh_timeline":
        count = output.get("event_count")
        return VerificationResult(True, f"Cache primed ({count} events).") if count is not None else VerificationResult(
            False, "Missing event count."
        )

    if tool_name in {"events_for_day", "events_between"}:
        events = output.get("events")
        if isinstance(events, list):
            return VerificationResult(True, f"Returned {len(events)} events.")
        return VerificationResult(False, "Missing events list.")

    if tool_name == "upsert_event":
        event = output.get("event") if isinstance(output, dict) else None
        if event and event.get("id"):
            return VerificationResult(True, f"Event saved ({event.get('title', 'untitled')}).")
        return VerificationResult(False, "Event payload missing id.")

    if tool_name == "delete_event":
        return VerificationResult(True, f"Deleted {output.get('deleted')}.") if output.get("deleted") else VerificationResult(
            False, "Delete acknowledgement missing."
        )

    if tool_name == "list_categories":
        categories = output.get("categories")
        if isinstance(categories, list):
            return VerificationResult(True, f"Returned {len(categories)} categories.")
        return VerificationResult(False, "Missing categories list.")

    if tool_name == "upsert_category":
        category = output.get("category")
        if category and category.get("id"):
            return VerificationResult(True, f"Category saved ({category.get('name', 'unnamed')}).")
        return VerificationResult(False, "Category payload missing id.")

    if tool_name == "delete_category":
        return VerificationResult(True, f"Deleted {output.get('deleted')}.") if output.get("deleted") else VerificationResult(
            False, "Delete acknowledgement missing."
        )

    return VerificationResult(True, "Ran without explicit verifier.")
