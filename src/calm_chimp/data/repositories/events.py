from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ...domain import CalendarEvent
from ..supabase import SupabaseGateway


@dataclass(slots=True)
class EventRepository:
    gateway: SupabaseGateway
    table_name: str
    categories_table: str

    def _select_clause(self) -> str:
        return f"*, category:{self.categories_table}(*)" if self.categories_table else "*"

    def fetch_window(self, user_id: str, start: datetime, end: datetime) -> List[CalendarEvent]:
        query = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .select(self._select_clause())
            .eq("user_id", user_id)
            .gte("starts_at", start.isoformat())
            .lte("ends_at", end.isoformat())
            .order("starts_at", desc=False)
        )
        response = query.execute()
        records = response.data or []
        events: list[CalendarEvent] = []
        for record in records:
            category_payload = record.pop("category", None)
            events.append(CalendarEvent.from_record(record, category=category_payload))
        return events

    def upsert(self, event: CalendarEvent) -> CalendarEvent:
        payload = event.to_record()
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .upsert(payload, on_conflict="id")
            .select(self._select_clause())
            .single()
            .execute()
        )
        data = response.data or payload
        category_payload = data.pop("category", None)
        return CalendarEvent.from_record(data, category=category_payload)

    def delete(self, event_id: str) -> bool:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .delete()
            .eq("id", event_id)
            .execute()
        )
        deleted = response.data or []
        return bool(deleted)

    def patch_metadata(self, event_id: str, metadata: dict) -> Optional[CalendarEvent]:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .update({"metadata": metadata})
            .eq("id", event_id)
            .select(self._select_clause())
            .single()
            .execute()
        )
        if not response.data:
            return None
        data = response.data
        category_payload = data.pop("category", None)
        return CalendarEvent.from_record(data, category=category_payload)
