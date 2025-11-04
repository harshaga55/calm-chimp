from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import orjson

from .config import DATA_DIR, ensure_data_dir


CALENDAR_STATE_FILE = DATA_DIR / "calendar_state.json"

DEFAULT_CALENDAR_STATE: Dict[str, Any] = {
    "calendars": [],
    "events": [],
    "templates": [],
    "tags": [],
    "preferences": {
        "timezone": "UTC",
        "week_start": "Monday",
        "default_calendar_id": None,
        "work_hours": {"start": "09:00", "end": "17:00"},
        "default_duration": 60,
    },
    "subscriptions": [],
    "webhooks": [],
    "notifications": [],
    "sync": {
        "next_token": 1,
        "changes": [],
        "last_ack": None,
        "clock": 0,
    },
    "imports": [],
    "exports": [],
    "audit": [],
    "trash": [],
    "counters": {
        "calendar": 0,
        "event": 0,
        "template": 0,
        "tag": 0,
        "note": 0,
        "checklist": 0,
        "attachment": 0,
        "webhook": 0,
        "audit": 0,
        "subscription": 0,
    },
}


class CalendarStore:
    """Lightweight persistence layer for calendar-centric data."""

    def __init__(self, path: Optional[Path] = None) -> None:
        ensure_data_dir()
        self._path = path or CALENDAR_STATE_FILE
        self._state: Optional[Dict[str, Any]] = None

    def _ensure_materialized(self) -> None:
        if self._state is not None:
            return
        if not self._path.exists():
            ensure_data_dir()
            payload = orjson.dumps(DEFAULT_CALENDAR_STATE, option=orjson.OPT_INDENT_2)
            self._path.write_bytes(payload + b"\n")
            self._state = deepcopy(DEFAULT_CALENDAR_STATE)
            return
        raw = self._path.read_bytes()
        if not raw:
            self._state = deepcopy(DEFAULT_CALENDAR_STATE)
            return
        self._state = orjson.loads(raw)
        # Backfill missing keys when upgrading.
        for key, value in DEFAULT_CALENDAR_STATE.items():
            if key not in self._state:
                self._state[key] = deepcopy(value)
        if "counters" not in self._state:
            self._state["counters"] = deepcopy(DEFAULT_CALENDAR_STATE["counters"])

    @property
    def data(self) -> Dict[str, Any]:
        self._ensure_materialized()
        assert self._state is not None
        return self._state

    def persist(self) -> None:
        if self._state is None:
            return
        payload = orjson.dumps(self._state, option=orjson.OPT_INDENT_2)
        self._path.write_bytes(payload + b"\n")

    def mutate(self, callback: Callable[[Dict[str, Any]], Any]) -> Any:
        self._ensure_materialized()
        assert self._state is not None
        result = callback(self._state)
        self.persist()
        return result

    def consume_id(self, state: Dict[str, Any], prefix: str) -> str:
        counters = state.setdefault("counters", {})
        current = counters.get(prefix, 0) + 1
        counters[prefix] = current
        return f"{prefix}_{current:04d}"

    def next_id(self, prefix: str) -> str:
        def _increment(state: Dict[str, Any]) -> str:
            return self.consume_id(state, prefix)

        return self.mutate(_increment)

    def bump_clock(self, delta: int = 1) -> int:
        def _advance(state: Dict[str, Any]) -> int:
            state.setdefault("sync", {}).setdefault("clock", 0)
            state["sync"]["clock"] += delta
            return state["sync"]["clock"]

        return self.mutate(_advance)

    @staticmethod
    def utc_now() -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def record_audit(self, action: str, *, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        def _append(state: Dict[str, Any]) -> Dict[str, Any]:
            entry_id = self._ensure_audit_counter(state)
            entry = {
                "id": entry_id,
                "timestamp": self.utc_now(),
                "action": action,
                "metadata": metadata or {},
            }
            state.setdefault("audit", []).append(entry)
            state.setdefault("sync", {}).setdefault("changes", []).append(
                {
                    "token": self._next_token(state),
                    "action": action,
                    "metadata": metadata or {},
                    "timestamp": entry["timestamp"],
                }
            )
            return entry

        return self.mutate(_append)

    def _ensure_audit_counter(self, state: Dict[str, Any]) -> str:
        counters = state.setdefault("counters", {})
        current = counters.get("audit", 0) + 1
        counters["audit"] = current
        return f"audit_{current:06d}"

    def _next_token(self, state: Dict[str, Any]) -> str:
        sync = state.setdefault("sync", {})
        current = sync.get("next_token", 1)
        sync["next_token"] = current + 1
        return f"tok_{current:06d}"

    def new_token(self) -> str:
        return self.mutate(self._next_token)

    def acknowledge_token(self, token: str) -> None:
        def _ack(state: Dict[str, Any]) -> None:
            state.setdefault("sync", {})["last_ack"] = token

        self.mutate(_ack)


__all__ = ["CalendarStore", "CALENDAR_STATE_FILE", "DEFAULT_CALENDAR_STATE"]
