from __future__ import annotations

from typing import Any, Dict

from ..domain import CalendarEvent, Category
from .models import CategoryPayload, EventPayload


def serialize_category(category: Category) -> Dict[str, Any]:
    return CategoryPayload.from_domain(category).model_dump()


def serialize_event(event: CalendarEvent) -> Dict[str, Any]:
    return EventPayload.from_domain(event).model_dump()
