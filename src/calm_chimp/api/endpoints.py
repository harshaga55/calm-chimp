from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from ..domain import EventStatus
from .registry import register_api
from .serializers import serialize_category, serialize_event
from .state import api_state


def _require_session() -> None:
    if not api_state.context.gateway.is_ready():
        raise RuntimeError("Supabase session is not initialized. Authenticate before calling API functions.")


def _parse_datetime(timestamp: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:  # noqa: TRY003
        raise ValueError(f"Invalid ISO timestamp: {timestamp}") from exc


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # noqa: TRY003
        raise ValueError(f"Invalid ISO date: {value}") from exc


@register_api(
    "refresh_timeline",
    description="Hydrate the Supabase-backed event cache for the configured time window.",
    category="calendar",
    tags=("cache", "supabase"),
)
def refresh_timeline(anchor: Optional[str] = None) -> Dict[str, Any]:
    _require_session()
    anchor_dt = _parse_datetime(anchor) if anchor else None
    api_state.calendar.prime_cache(anchor=anchor_dt)
    cache = api_state.calendar.cache
    return {
        "window_start": cache.window_start.isoformat(),
        "window_end": cache.window_end.isoformat(),
        "event_count": len(cache.events_by_id),
    }


@register_api(
    "events_for_day",
    description="Return all cached events for a specific day.",
    category="calendar",
    tags=("read",),
)
def events_for_day(day: str) -> Dict[str, Any]:
    _require_session()
    target = _parse_date(day)
    events = api_state.calendar.list_for_day(target)
    return {"day": target.isoformat(), "events": [serialize_event(event) for event in events]}


@register_api(
    "events_between",
    description="Return cached events between the inclusive date range.",
    category="calendar",
    tags=("read",),
)
def events_between(start: str, end: str) -> Dict[str, Any]:
    _require_session()
    start_day = _parse_date(start)
    end_day = _parse_date(end)
    events = api_state.calendar.list_between(start_day, end_day)
    return {
        "start": start_day.isoformat(),
        "end": end_day.isoformat(),
        "events": [serialize_event(event) for event in events],
    }


@register_api(
    "upsert_event",
    description="Create or update a calendar event in Supabase and refresh the cache.",
    category="calendar",
    tags=("write",),
)
def upsert_event(
    *,
    title: str,
    starts_at: str,
    ends_at: str,
    event_id: Optional[str] = None,
    status: str = EventStatus.PLANNED.value,
    category_id: Optional[str] = None,
    notes: str = "",
    location: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _require_session()
    status_enum = EventStatus(status)
    event = api_state.calendar.upsert_event(
        event_id=event_id,
        title=title,
        starts_at=_parse_datetime(starts_at),
        ends_at=_parse_datetime(ends_at),
        status=status_enum,
        category_id=category_id,
        notes=notes,
        location=location,
        metadata=metadata or {},
    )
    return {"event": serialize_event(event)}


@register_api(
    "update_event_status",
    description="Change the status of an existing event.",
    category="calendar",
    tags=("write",),
)
def update_event_status(event_id: str, status: str) -> Dict[str, Any]:
    _require_session()
    updated = api_state.calendar.update_status(event_id, EventStatus(status))
    if not updated:
        raise ValueError(f"Event '{event_id}' not found in cache.")
    return {"event": serialize_event(updated)}


@register_api(
    "delete_event",
    description="Remove an event from Supabase and the in-memory cache.",
    category="calendar",
    tags=("write",),
)
def delete_event(event_id: str) -> Dict[str, Any]:
    _require_session()
    deleted = api_state.calendar.delete_event(event_id)
    if not deleted:
        raise ValueError(f"Event '{event_id}' not found.")
    return {"deleted": event_id}


@register_api(
    "list_categories",
    description="List all categories for the current user.",
    category="categories",
    tags=("read",),
)
def list_categories() -> Dict[str, Any]:
    _require_session()
    categories = api_state.categories.list_categories()
    return {"categories": [serialize_category(category) for category in categories]}


@register_api(
    "upsert_category",
    description="Create or update an event category.",
    category="categories",
    tags=("write",),
)
def upsert_category(
    *,
    name: str,
    category_id: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    description: str = "",
) -> Dict[str, Any]:
    _require_session()
    category = api_state.categories.upsert_category(
        category_id=category_id,
        name=name,
        color=color,
        icon=icon,
        description=description,
    )
    return {"category": serialize_category(category)}


@register_api(
    "delete_category",
    description="Delete an event category.",
    category="categories",
    tags=("write",),
)
def delete_category(category_id: str) -> Dict[str, Any]:
    _require_session()
    deleted = api_state.categories.delete_category(category_id)
    if not deleted:
        raise ValueError(f"Category '{category_id}' not found.")
    return {"deleted": category_id}


@register_api(
    "current_user_profile",
    description="Fetch the current user's profile record from Supabase.",
    category="accounts",
    tags=("read",),
)
def current_user_profile() -> Dict[str, Any]:
    _require_session()
    user_id = api_state.context.gateway.current_user_id()
    profile = api_state.context.profiles.fetch(user_id)
    if not profile:
        session = api_state.context.gateway.session()
        email = getattr(getattr(session, "user", None), "email", None)
        return {"profile": {"id": user_id, "email": email}}
    return {
        "profile": {
            "id": profile.id,
            "email": profile.email,
            "full_name": profile.full_name,
            "avatar_url": profile.avatar_url,
        }
    }
