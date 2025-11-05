from __future__ import annotations

from typing import Any, Dict

from ..domain import CalendarEvent, Category


def serialize_category(category: Category) -> Dict[str, Any]:
    return {
        "id": category.id,
        "user_id": category.user_id,
        "name": category.name,
        "color": category.color,
        "icon": category.icon,
        "description": category.description,
    }


def serialize_event(event: CalendarEvent) -> Dict[str, Any]:
    payload = {
        "id": event.id,
        "user_id": event.user_id,
        "title": event.title,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "status": event.status.value,
        "category_id": event.category_id,
        "notes": event.notes,
        "location": event.location,
        "metadata": event.metadata,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }
    if event.category:
        payload["category"] = serialize_category(event.category)
    return payload
