from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional
from uuid import uuid4

from ..domain import CalendarEvent, EventStatus
from ..domain.models import Category
from ..data.cache import TimelineCache
from .context import ServiceContext


@dataclass(slots=True)
class CalendarService:
    context: ServiceContext

    @property
    def cache(self) -> TimelineCache:
        return self.context.cache

    def prime_cache(self, *, anchor: Optional[datetime] = None) -> None:
        """Hydrate the cache with the configured window relative to ``anchor``."""

        user_id = self.context.gateway.current_user_id()
        anchor_ts = anchor or datetime.utcnow()
        window_start = anchor_ts - self.context.settings.cache.window_before
        window_end = anchor_ts + self.context.settings.cache.window_after
        events = self.context.events.fetch_window(user_id, window_start, window_end)
        self.cache.hydrate(events, anchor=anchor_ts)

    def list_for_day(self, target_day: date) -> list[CalendarEvent]:
        return sorted(self.cache.events_for_day(target_day), key=lambda ev: ev.starts_at)

    def list_between(self, start: date, end: date) -> list[CalendarEvent]:
        return sorted(self.cache.events_between(start, end), key=lambda ev: ev.starts_at)

    def upsert_event(
        self,
        *,
        event_id: Optional[str],
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        status: EventStatus = EventStatus.PLANNED,
        category: Optional[Category] = None,
        category_id: Optional[str] = None,
        notes: str = "",
        location: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> CalendarEvent:
        user_id = self.context.gateway.current_user_id()
        identifier = event_id or str(uuid4())
        payload = CalendarEvent(
            id=identifier,
            user_id=user_id,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
            category=category,
            category_id=category_id or (category.id if category else None),
            notes=notes,
            location=location,
            metadata=metadata or {},
        )
        saved = self.context.events.upsert(payload)
        self.cache.upsert(saved)
        return saved

    def delete_event(self, event_id: str) -> bool:
        deleted = self.context.events.delete(event_id)
        if deleted:
            self.cache.remove(event_id)
        return deleted

    def update_status(self, event_id: str, status: EventStatus) -> Optional[CalendarEvent]:
        existing = self.cache.events_by_id.get(event_id)
        if not existing:
            return None
        updated = self.context.events.upsert(
            CalendarEvent(
                id=existing.id,
                user_id=existing.user_id,
                title=existing.title,
                starts_at=existing.starts_at,
                ends_at=existing.ends_at,
                status=status,
                category=existing.category,
                category_id=existing.category_id,
                notes=existing.notes,
                location=existing.location,
                metadata=existing.metadata,
            )
        )
        self.cache.upsert(updated)
        return updated

    def bulk_import(self, events: Iterable[CalendarEvent]) -> None:
        for event in events:
            self.context.events.upsert(event)
        self.prime_cache()
