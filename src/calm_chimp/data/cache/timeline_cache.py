from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List

from ...domain import CalendarEvent


def _date_range(start: date, end: date) -> Iterable[date]:
    delta = (end - start).days
    for index in range(delta + 1):
        yield start + timedelta(days=index)


@dataclass
class TimelineCache:
    """In-memory representation of a user's calendar window."""

    window_before: timedelta
    window_after: timedelta
    max_results: int
    events_by_id: Dict[str, CalendarEvent] = field(default_factory=dict)
    days_index: Dict[date, List[str]] = field(default_factory=dict)
    window_start: date = field(default_factory=lambda: datetime.utcnow().date())
    window_end: date = field(default_factory=lambda: datetime.utcnow().date())

    def reset_window(self, anchor: datetime | None = None) -> None:
        anchor_date = (anchor or datetime.utcnow()).date()
        self.window_start = anchor_date - self.window_before
        self.window_end = anchor_date + self.window_after

    def hydrate(self, events: Iterable[CalendarEvent], *, anchor: datetime | None = None) -> None:
        self.reset_window(anchor)
        self.events_by_id.clear()
        self.days_index.clear()

        sorted_events = sorted(events, key=lambda item: item.starts_at)[: self.max_results]
        for event in sorted_events:
            self._index_event(event)

    def _index_event(self, event: CalendarEvent) -> None:
        self.events_by_id[event.id] = event
        for day in _date_range(event.starts_at.date(), event.ends_at.date()):
            self.days_index.setdefault(day, []).append(event.id)

    def upsert(self, event: CalendarEvent) -> None:
        if event.id in self.events_by_id:
            self._remove_event(event.id)
        self._index_event(event)

    def _remove_event(self, event_id: str) -> None:
        if event_id not in self.events_by_id:
            return
        event = self.events_by_id.pop(event_id)
        for day in _date_range(event.starts_at.date(), event.ends_at.date()):
            ids = self.days_index.get(day, [])
            if event_id in ids:
                ids.remove(event_id)
            if not ids:
                self.days_index.pop(day, None)

    def remove(self, event_id: str) -> bool:
        if event_id not in self.events_by_id:
            return False
        self._remove_event(event_id)
        return True

    def events_for_day(self, target_day: date) -> List[CalendarEvent]:
        identifiers = self.days_index.get(target_day, [])
        return [self.events_by_id[event_id] for event_id in identifiers]

    def events_between(self, start: date, end: date) -> List[CalendarEvent]:
        collected: list[CalendarEvent] = []
        for day in _date_range(start, end):
            collected.extend(self.events_for_day(day))
        # remove duplicates while preserving order
        seen: set[str] = set()
        deduped: list[CalendarEvent] = []
        for event in collected:
            if event.id in seen:
                continue
            seen.add(event.id)
            deduped.append(event)
        return deduped

    def clear(self) -> None:
        self.events_by_id.clear()
        self.days_index.clear()
