from __future__ import annotations

import re
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from calendar import month_abbr, month_name

from ..core.calendar_store import CalendarStore
from .registry import register_api


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError("datetime must be ISO 8601 format") from exc


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


_MONTH_LOOKUP = {
    name.lower(): idx
    for idx, name in enumerate(month_name)
    if name
}
_MONTH_LOOKUP.update(
    {
        abbr.lower(): idx
        for idx, abbr in enumerate(month_abbr)
        if abbr
    }
)


def _strip_ordinal(text: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text.lower())


def _parse_quick_date(text: str, reference: Optional[date] = None) -> date:
    reference = reference or date.today()
    cleaned = _strip_ordinal(text.strip())
    if not cleaned:
        raise ValueError("date text is required")
    # Try ISO first
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    cleaned = cleaned.replace(",", " ")
    tokens = [token for token in cleaned.split() if token]
    month: Optional[int] = None
    day: Optional[int] = None
    year: Optional[int] = None
    for token in tokens:
        if token.isdigit():
            value = int(token)
            if day is None:
                day = value
            elif year is None:
                year = value
        elif token in _MONTH_LOOKUP:
            month = _MONTH_LOOKUP[token]
    if day is None:
        raise ValueError("Could not determine day from date text")
    if month is None:
        month = reference.month
    if year is None:
        year = reference.year
    try:
        candidate = date(year, month, day)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError("Could not parse provided date text") from exc
    if candidate < reference:
        # roll forward to next month/year if ambiguous date already passed
        new_month = month + 1
        new_year = year
        if new_month > 12:
            new_month = 1
            new_year += 1
        try:
            candidate = date(new_year, new_month, day)
        except ValueError:
            candidate = date(new_year, new_month, min(day, 28))
    return candidate


def _parse_quick_time(text: Optional[str]) -> time:
    if not text:
        return time(hour=9, minute=0)
    cleaned = text.strip().lower()
    if cleaned in {"morning", "am"}:
        return time(hour=9, minute=0)
    if cleaned in {"afternoon", "pm"}:
        return time(hour=15, minute=0)
    match = re.match(r"(?P<hour>\d{1,2})(:(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?", cleaned)
    if not match:
        raise ValueError("Could not understand time text")
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    ampm = match.group("ampm")
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour >= 24:
        raise ValueError("hour must be between 0 and 23")
    return time(hour=hour, minute=minute)


class CalendarService:
    def __init__(self, store: Optional[CalendarStore] = None) -> None:
        self.store = store or CalendarStore()

    # Calendar operations -------------------------------------------------
    def calendar_create(self, name: str) -> Dict[str, Any]:
        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            calendar_id = self.store.consume_id(state, "calendar")
            now = CalendarStore.utc_now()
            calendar = {
                "id": calendar_id,
                "name": name,
                "color": None,
                "timezone": state["preferences"].get("timezone", "UTC"),
                "is_default": False,
                "deleted": False,
                "archived": False,
                "created_at": now,
                "updated_at": now,
                "settings": {
                    "ics_published": False,
                    "privacy_busy_only": False,
                },
                "acl": [],
            }
            state.setdefault("calendars", []).append(calendar)
            if state["preferences"].get("default_calendar_id") is None:
                calendar["is_default"] = True
                state["preferences"]["default_calendar_id"] = calendar_id
            return calendar

        calendar = self.store.mutate(_create)
        self.store.record_audit("calendar.create", metadata={"calendar_id": calendar["id"]})
        return calendar

    def calendar_get(self, calendar_id: str) -> Dict[str, Any]:
        calendars = self.store.data.get("calendars", [])
        for calendar in calendars:
            if calendar["id"] == calendar_id:
                return calendar
        raise ValueError(f"Calendar {calendar_id} not found")

    def calendar_list(self) -> List[Dict[str, Any]]:
        return [cal for cal in self.store.data.get("calendars", []) if not cal.get("deleted")]

    def calendar_update(self, calendar_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        def _update(state: Dict[str, Any]) -> Dict[str, Any]:
            for calendar in state.get("calendars", []):
                if calendar["id"] == calendar_id:
                    if "settings" in updates:
                        current_settings = calendar.setdefault("settings", {})
                        current_settings.update(updates.get("settings", {}))
                    direct_updates = {key: value for key, value in updates.items() if key != "settings"}
                    calendar.update(direct_updates)
                    calendar["updated_at"] = CalendarStore.utc_now()
                    return calendar
            raise ValueError(f"Calendar {calendar_id} not found")

        calendar = self.store.mutate(_update)
        self.store.record_audit("calendar.update", metadata={"calendar_id": calendar_id, "changes": updates})
        return calendar

    def calendar_set_default(self, calendar_id: str) -> Dict[str, Any]:
        def _set_default(state: Dict[str, Any]) -> Dict[str, Any]:
            target = None
            for calendar in state.get("calendars", []):
                calendar["is_default"] = calendar["id"] == calendar_id
                if calendar["id"] == calendar_id:
                    target = calendar
                    calendar["updated_at"] = CalendarStore.utc_now()
            if not target:
                raise ValueError(f"Calendar {calendar_id} not found")
            state["preferences"]["default_calendar_id"] = calendar_id
            return target

        calendar = self.store.mutate(_set_default)
        self.store.record_audit("calendar.set_default", metadata={"calendar_id": calendar_id})
        return calendar

    def calendar_copy(self, calendar_id: str, name: str) -> Dict[str, Any]:
        def _copy(state: Dict[str, Any]) -> Dict[str, Any]:
            source = None
            for calendar in state.get("calendars", []):
                if calendar["id"] == calendar_id:
                    source = calendar
                    break
            if not source:
                raise ValueError(f"Calendar {calendar_id} not found")
            new_id = self.store.consume_id(state, "calendar")
            now = CalendarStore.utc_now()
            replica = {
                "id": new_id,
                "name": name,
                "color": source.get("color"),
                "timezone": source.get("timezone"),
                "is_default": False,
                "deleted": False,
                "archived": False,
                "created_at": now,
                "updated_at": now,
                "settings": source.get("settings", {}).copy(),
                "acl": [acl.copy() for acl in source.get("acl", [])],
            }
            state.setdefault("calendars", []).append(replica)
            # Duplicate events
            clone_events = []
            for event in state.get("events", []):
                if event.get("calendar_id") != calendar_id or event.get("deleted"):
                    continue
                cloned_event = deepcopy(event)
                cloned_event["id"] = self.store.consume_id(state, "event")
                cloned_event["calendar_id"] = new_id
                cloned_event["title"] = f"{cloned_event.get('title', '')} (Copy)".strip()
                cloned_event["created_at"] = now
                cloned_event["updated_at"] = now
                clone_events.append(cloned_event)
            state.setdefault("events", []).extend(clone_events)
            return replica

        calendar = self.store.mutate(_copy)
        self.store.record_audit("calendar.copy", metadata={"calendar_id": calendar_id, "new_calendar": calendar["id"]})
        return calendar

    def calendar_delete(self, calendar_id: str) -> Dict[str, Any]:
        def _delete(state: Dict[str, Any]) -> Dict[str, Any]:
            for calendar in state.get("calendars", []):
                if calendar["id"] == calendar_id:
                    calendar["deleted"] = True
                    calendar["updated_at"] = CalendarStore.utc_now()
                    state.setdefault("trash", []).append({"type": "calendar", "id": calendar_id})
                    return calendar
            raise ValueError(f"Calendar {calendar_id} not found")

        calendar = self.store.mutate(_delete)
        self.store.record_audit("calendar.delete", metadata={"calendar_id": calendar_id})
        return calendar

    def calendar_restore(self, calendar_id: str) -> Dict[str, Any]:
        def _restore(state: Dict[str, Any]) -> Dict[str, Any]:
            for calendar in state.get("calendars", []):
                if calendar["id"] == calendar_id:
                    calendar["deleted"] = False
                    calendar["updated_at"] = CalendarStore.utc_now()
                    state.setdefault("trash", [])[:] = [item for item in state.get("trash", []) if not (item.get("type") == "calendar" and item.get("id") == calendar_id)]
                    return calendar
            raise ValueError(f"Calendar {calendar_id} not found")

        calendar = self.store.mutate(_restore)
        self.store.record_audit("calendar.restore", metadata={"calendar_id": calendar_id})
        return calendar

    # Event helpers -------------------------------------------------------
    def _ensure_calendar_exists(self, state: Dict[str, Any], calendar_id: str) -> Dict[str, Any]:
        for calendar in state.get("calendars", []):
            if calendar["id"] == calendar_id and not calendar.get("deleted"):
                return calendar
        raise ValueError(f"Calendar {calendar_id} not found")

    def _ensure_event_exists(self, state: Dict[str, Any], event_id: str) -> Dict[str, Any]:
        for event in state.get("events", []):
            if event["id"] == event_id:
                return event
        raise ValueError(f"Event {event_id} not found")

    def _normalize_event(self, event: Dict[str, Any]) -> None:
        event.setdefault("description", "")
        event.setdefault("status", "confirmed")
        event.setdefault("transparency", "busy")
        event.setdefault("reminders", [])
        event.setdefault("attendees", [])
        event.setdefault("tags", [])
        event.setdefault("location", {"text": None, "lat": None, "lon": None})
        event.setdefault("attachments", [])
        event.setdefault("notes", [])
        event.setdefault("checklist", [])
        event.setdefault("recurrence", {})
        event.setdefault("instances", {})
        event.setdefault("focus", None)
        event.setdefault("deleted", False)
        event.setdefault("cancelled", False)
        event.setdefault("trashed_at", None)
        event.setdefault("color", None)

    def event_create(self, calendar_id: str, title: str, start: str, end: str) -> Dict[str, Any]:
        start_dt = _parse_datetime(start)
        end_dt = _parse_datetime(end)
        if end_dt <= start_dt:
            raise ValueError("end must be after start")

        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            self._ensure_calendar_exists(state, calendar_id)
            event_id = self.store.consume_id(state, "event")
            now = CalendarStore.utc_now()
            event = {
                "id": event_id,
                "calendar_id": calendar_id,
                "title": title,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "all_day": False,
                "date": None,
                "created_at": now,
                "updated_at": now,
            }
            self._normalize_event(event)
            state.setdefault("events", []).append(event)
            return event

        event = self.store.mutate(_create)
        self.store.record_audit("event.create", metadata={"event_id": event["id"], "calendar_id": calendar_id})
        return event

    def event_create_all_day(self, calendar_id: str, title: str, date_str: str) -> Dict[str, Any]:
        day = _parse_date(date_str)

        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            self._ensure_calendar_exists(state, calendar_id)
            event_id = self.store.consume_id(state, "event")
            now = CalendarStore.utc_now()
            event = {
                "id": event_id,
                "calendar_id": calendar_id,
                "title": title,
                "start": datetime.combine(day, time.min).isoformat(),
                "end": datetime.combine(day, time.max).isoformat(),
                "all_day": True,
                "date": day.isoformat(),
                "created_at": now,
                "updated_at": now,
            }
            self._normalize_event(event)
            state.setdefault("events", []).append(event)
            return event

        event = self.store.mutate(_create)
        self.store.record_audit("event.create_all_day", metadata={"event_id": event["id"], "calendar_id": calendar_id})
        return event

    def event_get(self, event_id: str) -> Dict[str, Any]:
        events = self.store.data.get("events", [])
        for event in events:
            if event["id"] == event_id:
                return event
        raise ValueError(f"Event {event_id} not found")

    def event_update_fields(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        def _update(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event.update(updates)
            event["updated_at"] = CalendarStore.utc_now()
            return event

        event = self.store.mutate(_update)
        self.store.record_audit("event.update", metadata={"event_id": event_id, "changes": updates})
        return event

    def event_move(self, event_id: str, target_calendar_id: str) -> Dict[str, Any]:
        def _move(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            self._ensure_calendar_exists(state, target_calendar_id)
            event["calendar_id"] = target_calendar_id
            event["updated_at"] = CalendarStore.utc_now()
            return event

        event = self.store.mutate(_move)
        self.store.record_audit("event.move", metadata={"event_id": event_id, "calendar_id": target_calendar_id})
        return event

    def event_duplicate(self, event_id: str, target_calendar_id: str) -> Dict[str, Any]:
        def _duplicate(state: Dict[str, Any]) -> Dict[str, Any]:
            original = self._ensure_event_exists(state, event_id)
            self._ensure_calendar_exists(state, target_calendar_id)
            new_id = self.store.consume_id(state, "event")
            now = CalendarStore.utc_now()
            clone = deepcopy(original)
            clone["id"] = new_id
            clone["calendar_id"] = target_calendar_id
            clone["title"] = f"{clone.get('title', '')} (Copy)".strip()
            clone["created_at"] = now
            clone["updated_at"] = now
            state.setdefault("events", []).append(clone)
            return clone

        event = self.store.mutate(_duplicate)
        self.store.record_audit(
            "event.duplicate", metadata={"source_event": event_id, "new_event": event["id"], "calendar_id": target_calendar_id}
        )
        return event

    def event_cancel(self, event_id: str) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"status": "cancelled", "cancelled": True})

    def event_delete(self, event_id: str) -> Dict[str, Any]:
        def _delete(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["deleted"] = True
            event["trashed_at"] = CalendarStore.utc_now()
            event["updated_at"] = event["trashed_at"]
            state.setdefault("trash", []).append({"type": "event", "id": event_id})
            return event

        event = self.store.mutate(_delete)
        self.store.record_audit("event.delete", metadata={"event_id": event_id})
        return event

    def event_restore(self, event_id: str) -> Dict[str, Any]:
        def _restore(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["deleted"] = False
            event["cancelled"] = False
            event["trashed_at"] = None
            event["updated_at"] = CalendarStore.utc_now()
            state.setdefault("trash", [])[:] = [item for item in state.get("trash", []) if not (item.get("type") == "event" and item.get("id") == event_id)]
            return event

        event = self.store.mutate(_restore)
        self.store.record_audit("event.restore", metadata={"event_id": event_id})
        return event

    def event_set_color(self, event_id: str, color: str) -> Dict[str, Any]:
        def _set(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["color"] = color
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "color": color}

        result = self.store.mutate(_set)
        self.store.record_audit("event.set_color", metadata={"event_id": event_id, "color": color})
        return result

    # Event listing helpers ----------------------------------------------
    def _events_for_calendar(self, state: Dict[str, Any], calendar_id: str) -> List[Dict[str, Any]]:
        return [event for event in state.get("events", []) if event.get("calendar_id") == calendar_id and not event.get("deleted")]

    def event_list_between(self, calendar_id: str, start: date, end: date) -> List[Dict[str, Any]]:
        def _list(state: Dict[str, Any]) -> List[Dict[str, Any]]:
            events = self._events_for_calendar(state, calendar_id)
            results: List[Dict[str, Any]] = []
            for event in events:
                if event.get("all_day"):
                    event_date = _parse_date(event["date"]) if event.get("date") else None
                    if event_date and start <= event_date <= end:
                        results.append(event)
                    continue
                event_start = datetime.fromisoformat(event["start"])
                event_end = datetime.fromisoformat(event["end"])
                if event_start.date() <= end and event_end.date() >= start:
                    results.append(event)
            return results

        return self.store.mutate(_list)

    def event_list_day(self, calendar_id: str, day: date) -> List[Dict[str, Any]]:
        return self.event_list_between(calendar_id, day, day)

    def event_list_week(self, calendar_id: str, week_start: date) -> List[Dict[str, Any]]:
        return self.event_list_between(calendar_id, week_start, week_start + timedelta(days=6))

    def event_list_month(self, calendar_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        return self.event_list_between(calendar_id, start, end)

    def event_quick_add(
        self,
        *,
        title: str,
        date_text: str,
        time_text: Optional[str] = None,
        calendar_id: Optional[str] = None,
        duration_minutes: int = 60,
        notes: Optional[str] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        assumptions: List[str] = []
        target_calendar_id = calendar_id
        if not target_calendar_id:
            default = self.store.data.get("preferences", {}).get("default_calendar_id")
            if default:
                target_calendar_id = default
            else:
                calendars = self.store.data.get("calendars", [])
                if calendars:
                    target_calendar_id = calendars[0]["id"]
                    assumptions.append(f"Used calendar '{calendars[0]['name']}'")
                else:
                    created = self.calendar_create("General")
                    target_calendar_id = created["id"]
                    assumptions.append("Created default calendar 'General'")

        start_day = _parse_quick_date(date_text)
        start_time = _parse_quick_time(time_text)
        start_dt = datetime.combine(start_day, start_time)
        if duration_minutes <= 0:
            duration_minutes = 60
            assumptions.append("Duration reset to 60 minutes")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = self.event_create(
            target_calendar_id,
            title,
            start_dt.isoformat(),
            end_dt.isoformat(),
        )

        if attendees:
            for email in attendees:
                try:
                    self.attendee_add(event["id"], email)
                except ValueError:
                    continue
        if notes:
            self.note_add(event["id"], notes)

        if not time_text:
            assumptions.append("Defaulted start time to 09:00")
        if duration_minutes == 60:
            assumptions.append("Defaulted duration to 60 minutes")

        payload = {
            "event": event,
            "calendar_id": target_calendar_id,
            "assumptions": assumptions,
        }
        self.store.record_audit(
            "event.quick_add",
            metadata={
                "event_id": event["id"],
                "calendar_id": target_calendar_id,
                "duration_minutes": duration_minutes,
            },
        )
        return payload

    # Recurrence ----------------------------------------------------------
    def recurrence_update(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        def _update(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            recurrence = event.setdefault("recurrence", {})
            recurrence.update(updates)
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "recurrence": recurrence}

        result = self.store.mutate(_update)
        self.store.record_audit("event.recurrence.update", metadata={"event_id": event_id, "changes": updates})
        return result

    def recurrence_clear(self, event_id: str) -> Dict[str, Any]:
        def _clear(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["recurrence"] = {}
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "recurrence": {}}

        result = self.store.mutate(_clear)
        self.store.record_audit("event.recurrence.clear", metadata={"event_id": event_id})
        return result

    # Instances -----------------------------------------------------------
    def instance_update(self, series_id: str, occurrence_date: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        day = _parse_date(occurrence_date)

        def _update(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, series_id)
            instances = event.setdefault("instances", {})
            key = day.isoformat()
            override = instances.get(key, {"date": key})
            override.update(updates)
            instances[key] = override
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": series_id, "occurrence": override}

        result = self.store.mutate(_update)
        self.store.record_audit("event.instance.update", metadata={"event_id": series_id, "date": day.isoformat(), "changes": updates})
        return result

    def instance_get(self, series_id: str, occurrence_date: str) -> Dict[str, Any]:
        day = _parse_date(occurrence_date)
        event = self.event_get(series_id)
        return event.get("instances", {}).get(day.isoformat(), {})

    def instance_list(self, series_id: str, start: str, end: str) -> List[Dict[str, Any]]:
        start_day = _parse_date(start)
        end_day = _parse_date(end)
        event = self.event_get(series_id)
        instances = event.get("instances", {})
        return [instances[day.isoformat()] for day in _date_range(start_day, end_day) if day.isoformat() in instances]

    def instance_cancel(self, series_id: str, occurrence_date: str) -> Dict[str, Any]:
        return self.instance_update(series_id, occurrence_date, {"status": "cancelled"})

    def instance_skip(self, series_id: str, occurrence_date: str) -> Dict[str, Any]:
        return self.instance_update(series_id, occurrence_date, {"skip": True})

    def instance_detach(self, series_id: str, occurrence_date: str) -> Dict[str, Any]:
        day = _parse_date(occurrence_date)

        def _detach(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, series_id)
            key = day.isoformat()
            override = event.setdefault("instances", {}).get(key)
            if not override:
                raise ValueError("No override to detach")
            new_id = self.store.consume_id(state, "event")
            now = CalendarStore.utc_now()
            new_event = {
                **event,
                "id": new_id,
                "recurrence": {},
                "instances": {},
                "created_at": now,
                "updated_at": now,
            }
            new_event.update(override)
            new_event["calendar_id"] = event["calendar_id"]
            event["instances"].pop(key, None)
            state.setdefault("events", []).append(new_event)
            return {"event_id": new_id}

        result = self.store.mutate(_detach)
        self.store.record_audit("event.instance.detach", metadata={"event_id": series_id, "date": day.isoformat(), "new_event": result["event_id"]})
        return result

    def instance_restore(self, series_id: str, occurrence_date: str) -> Dict[str, Any]:
        day = _parse_date(occurrence_date)

        def _restore(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, series_id)
            event.setdefault("instances", {}).pop(day.isoformat(), None)
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": series_id, "date": day.isoformat()}

        result = self.store.mutate(_restore)
        self.store.record_audit("event.instance.restore", metadata={"event_id": series_id, "date": day.isoformat()})
        return result

    # Attendees -----------------------------------------------------------
    def attendee_add(self, event_id: str, email: str, optional: bool = False) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attendees = event.setdefault("attendees", [])
            if any(att.get("email") == email for att in attendees):
                raise ValueError("Attendee already exists")
            attendee = {
                "email": email,
                "optional": optional,
                "response": "none",
                "role": "required" if not optional else "optional",
                "name": None,
            }
            attendees.append(attendee)
            event["updated_at"] = CalendarStore.utc_now()
            return attendee

        attendee = self.store.mutate(_add)
        self.store.record_audit("event.attendee.add", metadata={"event_id": event_id, "email": email})
        return attendee

    def attendee_remove(self, event_id: str, email: str) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attendees = event.setdefault("attendees", [])
            before = len(attendees)
            attendees[:] = [att for att in attendees if att.get("email") != email]
            if before == len(attendees):
                raise ValueError("Attendee not found")
            event["updated_at"] = CalendarStore.utc_now()
            return {"removed": email}

        result = self.store.mutate(_remove)
        self.store.record_audit("event.attendee.remove", metadata={"event_id": event_id, "email": email})
        return result

    def attendee_list(self, event_id: str) -> List[Dict[str, Any]]:
        event = self.event_get(event_id)
        return event.get("attendees", [])

    def attendee_set(self, event_id: str, email: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        def _set(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attendees = event.setdefault("attendees", [])
            for attendee in attendees:
                if attendee.get("email") == email:
                    attendee.update(updates)
                    event["updated_at"] = CalendarStore.utc_now()
                    return attendee
            raise ValueError("Attendee not found")

        attendee = self.store.mutate(_set)
        self.store.record_audit("event.attendee.update", metadata={"event_id": event_id, "email": email, "changes": updates})
        return attendee

    # Reminders -----------------------------------------------------------
    def reminder_add(self, event_id: str, minutes: int) -> Dict[str, Any]:
        if minutes < 0:
            raise ValueError("minutes must be non-negative")

        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            reminders = event.setdefault("reminders", [])
            if minutes in reminders:
                raise ValueError("reminder already exists")
            reminders.append(minutes)
            reminders.sort()
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "minutes": minutes, "reminders": reminders}

        result = self.store.mutate(_add)
        self.store.record_audit("event.reminder.add", metadata={"event_id": event_id, "minutes": minutes})
        return result

    def reminder_remove(self, event_id: str, minutes: int) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            reminders = event.setdefault("reminders", [])
            if minutes not in reminders:
                raise ValueError("reminder not found")
            reminders[:] = [value for value in reminders if value != minutes]
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "minutes": minutes, "reminders": reminders}

        result = self.store.mutate(_remove)
        self.store.record_audit("event.reminder.remove", metadata={"event_id": event_id, "minutes": minutes})
        return result

    def reminder_list(self, event_id: str) -> List[int]:
        event = self.event_get(event_id)
        return sorted(event.get("reminders", []))

    def reminder_clear(self, event_id: str) -> Dict[str, Any]:
        def _clear(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["reminders"] = []
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "reminders": []}

        result = self.store.mutate(_clear)
        self.store.record_audit("event.reminder.clear", metadata={"event_id": event_id})
        return result

    def reminder_set_default(self, calendar_id: str, minutes: int) -> Dict[str, Any]:
        def _set(state: Dict[str, Any]) -> Dict[str, Any]:
            calendar = self._ensure_calendar_exists(state, calendar_id)
            calendar.setdefault("settings", {})["default_reminder"] = minutes
            calendar["updated_at"] = CalendarStore.utc_now()
            return {"calendar_id": calendar_id, "minutes": minutes}

        result = self.store.mutate(_set)
        self.store.record_audit("calendar.reminder.default", metadata={"calendar_id": calendar_id, "minutes": minutes})
        return result

    def reminder_snooze(self, event_id: str, minutes: int) -> Dict[str, Any]:
        def _snooze(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event.setdefault("snoozed", []).append({"minutes": minutes, "timestamp": CalendarStore.utc_now()})
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "minutes": minutes}

        result = self.store.mutate(_snooze)
        self.store.record_audit("event.reminder.snooze", metadata={"event_id": event_id, "minutes": minutes})
        return result

    # Availability --------------------------------------------------------
    def availability_free_busy(self, calendar_id: str, start: date, end: date) -> Dict[str, Any]:
        def _collect(state: Dict[str, Any]) -> Dict[str, Any]:
            events = self._events_for_calendar(state, calendar_id)
            busy: List[Dict[str, Any]] = []
            for event in events:
                if event.get("status") == "cancelled":
                    continue
                event_start = datetime.fromisoformat(event["start"])
                event_end = datetime.fromisoformat(event["end"])
                if event_end.date() < start or event_start.date() > end:
                    continue
                busy.append({"start": event_start.isoformat(), "end": event_end.isoformat(), "event_id": event["id"]})
            busy.sort(key=lambda item: item["start"])
            return {"calendar_id": calendar_id, "busy": busy, "range": {"start": start.isoformat(), "end": end.isoformat()}}

        return self.store.mutate(_collect)

    def availability_next_free_block(self, calendar_id: str, minutes: int) -> Dict[str, Any]:
        now = datetime.utcnow()
        target_delta = timedelta(minutes=minutes)

        def _find(state: Dict[str, Any]) -> Dict[str, Any]:
            events = self._events_for_calendar(state, calendar_id)
            busy = [
                (datetime.fromisoformat(event["start"]), datetime.fromisoformat(event["end"]))
                for event in events
                if event.get("status") != "cancelled"
            ]
            busy.sort(key=lambda span: span[0])
            cursor = now
            for start_dt, end_dt in busy:
                if end_dt <= cursor:
                    continue
                if start_dt - cursor >= target_delta:
                    break
                cursor = max(cursor, end_dt)
            slot = {"start": cursor.isoformat(), "end": (cursor + target_delta).isoformat(), "minutes": minutes}
            return {"calendar_id": calendar_id, "slot": slot}

        return self.store.mutate(_find)

    def availability_find_slot_on_day(self, calendar_id: str, day: date, minutes: int) -> Dict[str, Any]:
        start_dt = datetime.combine(day, time.min)
        end_dt = datetime.combine(day, time.max)
        window = timedelta(minutes=minutes)

        def _find(state: Dict[str, Any]) -> Dict[str, Any]:
            events = self._events_for_calendar(state, calendar_id)
            busy = [
                (datetime.fromisoformat(event["start"]), datetime.fromisoformat(event["end"]))
                for event in events
                if event.get("status") != "cancelled" and start_dt <= datetime.fromisoformat(event["start"]) <= end_dt
            ]
            busy.sort(key=lambda span: span[0])
            cursor = start_dt
            for start_span, end_span in busy:
                if start_span - cursor >= window:
                    break
                cursor = max(cursor, end_span)
            if end_dt - cursor < window:
                raise ValueError("No slot available")
            slot = {"start": cursor.isoformat(), "end": (cursor + window).isoformat(), "minutes": minutes}
            return {"calendar_id": calendar_id, "slot": slot}

        return self.store.mutate(_find)

    def availability_find_slot_in_week(self, calendar_id: str, week_start: date, minutes: int) -> Dict[str, Any]:
        for day in _date_range(week_start, week_start + timedelta(days=6)):
            try:
                return self.availability_find_slot_on_day(calendar_id, day, minutes)
            except ValueError:
                continue
        raise ValueError("No slot available this week")

    def availability_meeting_suggest(self, calendar_id: str, day: date, minutes: int) -> Dict[str, Any]:
        return self.availability_find_slot_on_day(calendar_id, day, minutes)

    def availability_busy_summary(self, calendar_id: str, day: date) -> Dict[str, Any]:
        events = self.event_list_day(calendar_id, day)
        total = 0
        for event in events:
            start_dt = datetime.fromisoformat(event["start"])
            end_dt = datetime.fromisoformat(event["end"])
            total += int((end_dt - start_dt).total_seconds() // 60)
        return {"calendar_id": calendar_id, "date": day.isoformat(), "busy_minutes": total}

    # Focus blocks --------------------------------------------------------
    def focus_create_block(self, calendar_id: str, title: str, day: str, minutes: int) -> Dict[str, Any]:
        block_start = datetime.combine(_parse_date(day), time(hour=9))
        block_end = block_start + timedelta(minutes=minutes)
        event = self.event_create(calendar_id, title, block_start.isoformat(), block_end.isoformat())
        return self.event_update_fields(event["id"], {"focus": {"minutes": minutes, "locked": False}})

    def focus_auto_plan_week(self, calendar_id: str, week_start: str) -> Dict[str, Any]:
        start_day = _parse_date(week_start)
        schedule: List[Dict[str, Any]] = []
        for day in _date_range(start_day, start_day + timedelta(days=4)):
            try:
                slot = self.availability_find_slot_on_day(calendar_id, day, 60)
            except ValueError:
                continue
            schedule.append({"date": day.isoformat(), "slot": slot["slot"]})
        return {"calendar_id": calendar_id, "week_start": start_day.isoformat(), "blocks": schedule}

    def focus_auto_plan_until(self, calendar_id: str, date_str: str) -> Dict[str, Any]:
        end_day = _parse_date(date_str)
        today = date.today()
        schedule: List[Dict[str, Any]] = []
        for day in _date_range(today, end_day):
            if day.weekday() >= 5:
                continue
            try:
                slot = self.availability_find_slot_on_day(calendar_id, day, 45)
            except ValueError:
                continue
            schedule.append({"date": day.isoformat(), "slot": slot["slot"]})
        return {"calendar_id": calendar_id, "until": end_day.isoformat(), "blocks": schedule}

    def focus_lock(self, event_id: str) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"focus": {"locked": True}})

    def focus_unlock(self, event_id: str) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"focus": {"locked": False}})

    def focus_defer(self, event_id: str, days: int) -> Dict[str, Any]:
        event = self.event_get(event_id)
        start_dt = datetime.fromisoformat(event["start"]) + timedelta(days=days)
        end_dt = datetime.fromisoformat(event["end"]) + timedelta(days=days)
        return self.event_update_fields(event_id, {"start": start_dt.isoformat(), "end": end_dt.isoformat()})

    def focus_bump(self, event_id: str) -> Dict[str, Any]:
        return self.focus_defer(event_id, 1)

    # Templates -----------------------------------------------------------
    def template_create(self, name: str, minutes: int) -> Dict[str, Any]:
        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            template_id = self.store.consume_id(state, "template")
            template = {"id": template_id, "name": name, "minutes": minutes}
            state.setdefault("templates", []).append(template)
            return template

        template = self.store.mutate(_create)
        self.store.record_audit("template.create", metadata={"template_id": template["id"]})
        return template

    def template_get(self, template_id: str) -> Dict[str, Any]:
        for template in self.store.data.get("templates", []):
            if template["id"] == template_id:
                return template
        raise ValueError(f"Template {template_id} not found")

    def template_list(self) -> List[Dict[str, Any]]:
        return list(self.store.data.get("templates", []))

    def template_rename(self, template_id: str, name: str) -> Dict[str, Any]:
        def _rename(state: Dict[str, Any]) -> Dict[str, Any]:
            for template in state.get("templates", []):
                if template["id"] == template_id:
                    template["name"] = name
                    return template
            raise ValueError(f"Template {template_id} not found")

        template = self.store.mutate(_rename)
        self.store.record_audit("template.rename", metadata={"template_id": template_id})
        return template

    def template_instantiate(self, template_id: str, calendar_id: str, day: str) -> Dict[str, Any]:
        template = self.template_get(template_id)
        block_start = datetime.combine(_parse_date(day), time(hour=9))
        block_end = block_start + timedelta(minutes=template["minutes"])
        event = self.event_create(calendar_id, template["name"], block_start.isoformat(), block_end.isoformat())
        self.store.record_audit(
            "template.instantiate",
            metadata={"template_id": template_id, "event_id": event["id"], "calendar_id": calendar_id},
        )
        return event

    # Tags ----------------------------------------------------------------
    def tag_create(self, name: str) -> Dict[str, Any]:
        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            tag_id = self.store.consume_id(state, "tag")
            tag = {"id": tag_id, "name": name}
            state.setdefault("tags", []).append(tag)
            return tag

        tag = self.store.mutate(_create)
        self.store.record_audit("tag.create", metadata={"tag_id": tag["id"]})
        return tag

    def tag_list(self) -> List[Dict[str, Any]]:
        return list(self.store.data.get("tags", []))

    def tag_rename(self, tag_id: str, name: str) -> Dict[str, Any]:
        def _rename(state: Dict[str, Any]) -> Dict[str, Any]:
            for tag in state.get("tags", []):
                if tag["id"] == tag_id:
                    tag["name"] = name
                    return tag
            raise ValueError(f"Tag {tag_id} not found")

        tag = self.store.mutate(_rename)
        self.store.record_audit("tag.rename", metadata={"tag_id": tag_id})
        return tag

    def tag_delete(self, tag_id: str) -> Dict[str, Any]:
        def _delete(state: Dict[str, Any]) -> Dict[str, Any]:
            before = len(state.get("tags", []))
            state["tags"] = [tag for tag in state.get("tags", []) if tag.get("id") != tag_id]
            if before == len(state.get("tags", [])):
                raise ValueError(f"Tag {tag_id} not found")
            for event in state.get("events", []):
                if tag_id in event.get("tags", []):
                    event["tags"] = [tid for tid in event.get("tags", []) if tid != tag_id]
            return {"removed": tag_id}

        result = self.store.mutate(_delete)
        self.store.record_audit("tag.delete", metadata={"tag_id": tag_id})
        return result

    def tag_add_to_event(self, event_id: str, tag_id: str) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            self._ensure_event_exists(state, event_id)
            tags = [tag["id"] for tag in state.get("tags", [])]
            if tag_id not in tags:
                raise ValueError(f"Tag {tag_id} not found")
            event = self._ensure_event_exists(state, event_id)
            event.setdefault("tags", [])
            if tag_id not in event["tags"]:
                event["tags"].append(tag_id)
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "tag_id": tag_id, "tags": event["tags"]}

        result = self.store.mutate(_add)
        self.store.record_audit("tag.attach", metadata={"event_id": event_id, "tag_id": tag_id})
        return result

    def tag_remove_from_event(self, event_id: str, tag_id: str) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event.setdefault("tags", [])
            event["tags"] = [tid for tid in event["tags"] if tid != tag_id]
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "tag_id": tag_id, "tags": event["tags"]}

        result = self.store.mutate(_remove)
        self.store.record_audit("tag.detach", metadata={"event_id": event_id, "tag_id": tag_id})
        return result

    # Locations -----------------------------------------------------------
    def location_set_text(self, event_id: str, text: str) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"location": {"text": text, "lat": None, "lon": None}})

    def location_set_coordinates(self, event_id: str, lat: float, lon: float) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"location": {"text": None, "lat": lat, "lon": lon}})

    def location_get(self, event_id: str) -> Dict[str, Any]:
        event = self.event_get(event_id)
        return event.get("location", {})

    def location_clear(self, event_id: str) -> Dict[str, Any]:
        return self.event_update_fields(event_id, {"location": {"text": None, "lat": None, "lon": None}})

    # Attachments ---------------------------------------------------------
    def attachment_add_url(self, event_id: str, url: str) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attachments = event.setdefault("attachments", [])
            attachment_id = self.store.consume_id(state, "attachment")
            attachments.append({"id": attachment_id, "type": "url", "url": url})
            event["updated_at"] = CalendarStore.utc_now()
            return attachments[-1]

        attachment = self.store.mutate(_add)
        self.store.record_audit("attachment.add_url", metadata={"event_id": event_id, "attachment_id": attachment["id"]})
        return attachment

    def attachment_add_file_ref(self, event_id: str, file_id: str) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attachments = event.setdefault("attachments", [])
            attachment_id = self.store.consume_id(state, "attachment")
            attachments.append({"id": attachment_id, "type": "file", "file_id": file_id})
            event["updated_at"] = CalendarStore.utc_now()
            return attachments[-1]

        attachment = self.store.mutate(_add)
        self.store.record_audit("attachment.add_file", metadata={"event_id": event_id, "attachment_id": attachment["id"]})
        return attachment

    def attachment_list(self, event_id: str) -> List[Dict[str, Any]]:
        event = self.event_get(event_id)
        return event.get("attachments", [])

    def attachment_remove(self, event_id: str, ref: str) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            attachments = event.setdefault("attachments", [])
            attachments[:] = [item for item in attachments if item.get("id") != ref]
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "removed": ref, "attachments": attachments}

        result = self.store.mutate(_remove)
        self.store.record_audit("attachment.remove", metadata={"event_id": event_id, "attachment_id": ref})
        return result

    def attachment_clear(self, event_id: str) -> Dict[str, Any]:
        def _clear(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            event["attachments"] = []
            event["updated_at"] = CalendarStore.utc_now()
            return {"event_id": event_id, "attachments": []}

        result = self.store.mutate(_clear)
        self.store.record_audit("attachment.clear", metadata={"event_id": event_id})
        return result

    # Notes & checklist ---------------------------------------------------
    def note_add(self, event_id: str, text: str) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            note_id = self.store.consume_id(state, "note")
            note = {"id": note_id, "text": text}
            event.setdefault("notes", []).append(note)
            event["updated_at"] = CalendarStore.utc_now()
            return note

        note = self.store.mutate(_add)
        self.store.record_audit("note.add", metadata={"event_id": event_id, "note_id": note["id"]})
        return note

    def note_list(self, event_id: str) -> List[Dict[str, Any]]:
        event = self.event_get(event_id)
        return event.get("notes", [])

    def note_update(self, note_id: str, text: str) -> Dict[str, Any]:
        def _update(state: Dict[str, Any]) -> Dict[str, Any]:
            for event in state.get("events", []):
                for note in event.setdefault("notes", []):
                    if note.get("id") == note_id:
                        note["text"] = text
                        event["updated_at"] = CalendarStore.utc_now()
                        return note
            raise ValueError(f"Note {note_id} not found")

        note = self.store.mutate(_update)
        self.store.record_audit("note.update", metadata={"note_id": note_id})
        return note

    def note_remove(self, note_id: str) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            for event in state.get("events", []):
                notes = event.setdefault("notes", [])
                for idx, note in enumerate(notes):
                    if note.get("id") == note_id:
                        notes.pop(idx)
                        event["updated_at"] = CalendarStore.utc_now()
                        return {"note_id": note_id}
            raise ValueError(f"Note {note_id} not found")

        result = self.store.mutate(_remove)
        self.store.record_audit("note.remove", metadata={"note_id": note_id})
        return result

    def checklist_toggle(self, event_id: str, item_id: str) -> Dict[str, Any]:
        def _toggle(state: Dict[str, Any]) -> Dict[str, Any]:
            event = self._ensure_event_exists(state, event_id)
            checklist = event.setdefault("checklist", [])
            for item in checklist:
                if item.get("id") == item_id:
                    item["checked"] = not item.get("checked", False)
                    event["updated_at"] = CalendarStore.utc_now()
                    return item
            new_item = {"id": item_id, "checked": True}
            checklist.append(new_item)
            event["updated_at"] = CalendarStore.utc_now()
            return new_item

        item = self.store.mutate(_toggle)
        self.store.record_audit("checklist.toggle", metadata={"event_id": event_id, "item_id": item_id})
        return item

    # Preferences ---------------------------------------------------------
    def prefs_get(self) -> Dict[str, Any]:
        return dict(self.store.data.get("preferences", {}))

    def prefs_set(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        def _set(state: Dict[str, Any]) -> Dict[str, Any]:
            state.setdefault("preferences", {}).update(updates)
            return dict(state["preferences"])

        prefs = self.store.mutate(_set)
        self.store.record_audit("prefs.update", metadata={"changes": updates})
        return prefs

    # ACL -----------------------------------------------------------------
    def acl_add(self, calendar_id: str, email: str, role: str) -> Dict[str, Any]:
        def _add(state: Dict[str, Any]) -> Dict[str, Any]:
            calendar = self._ensure_calendar_exists(state, calendar_id)
            acl = calendar.setdefault("acl", [])
            if any(entry.get("email") == email for entry in acl):
                raise ValueError("ACL entry already exists")
            entry = {"email": email, "role": role}
            acl.append(entry)
            calendar["updated_at"] = CalendarStore.utc_now()
            return entry

        entry = self.store.mutate(_add)
        self.store.record_audit("acl.add", metadata={"calendar_id": calendar_id, "email": email, "role": role})
        return entry

    def acl_remove(self, calendar_id: str, email: str) -> Dict[str, Any]:
        def _remove(state: Dict[str, Any]) -> Dict[str, Any]:
            calendar = self._ensure_calendar_exists(state, calendar_id)
            acl = calendar.setdefault("acl", [])
            before = len(acl)
            acl[:] = [entry for entry in acl if entry.get("email") != email]
            if before == len(acl):
                raise ValueError("ACL entry not found")
            calendar["updated_at"] = CalendarStore.utc_now()
            return {"email": email}

        result = self.store.mutate(_remove)
        self.store.record_audit("acl.remove", metadata={"calendar_id": calendar_id, "email": email})
        return result

    def acl_list(self, calendar_id: str) -> List[Dict[str, Any]]:
        calendar = self.calendar_get(calendar_id)
        return calendar.get("acl", [])

    def acl_set_role(self, calendar_id: str, email: str, role: str) -> Dict[str, Any]:
        def _set(state: Dict[str, Any]) -> Dict[str, Any]:
            calendar = self._ensure_calendar_exists(state, calendar_id)
            acl = calendar.setdefault("acl", [])
            for entry in acl:
                if entry.get("email") == email:
                    entry["role"] = role
                    calendar["updated_at"] = CalendarStore.utc_now()
                    return entry
            raise ValueError("ACL entry not found")

        entry = self.store.mutate(_set)
        self.store.record_audit("acl.set_role", metadata={"calendar_id": calendar_id, "email": email, "role": role})
        return entry

    def acl_publish_ics(self, calendar_id: str, enabled: bool) -> Dict[str, Any]:
        return self.calendar_update(calendar_id, {"settings": {"ics_published": enabled}})

    def acl_set_privacy(self, calendar_id: str, enabled: bool) -> Dict[str, Any]:
        return self.calendar_update(calendar_id, {"settings": {"privacy_busy_only": enabled}})

    # Sync ----------------------------------------------------------------
    def sync_delta_token_new(self) -> Dict[str, Any]:
        token = self.store.new_token()
        return {"token": token}

    def sync_pull_changes(self, since_token: str) -> Dict[str, Any]:
        changes = [
            change
            for change in self.store.data.get("sync", {}).get("changes", [])
            if change["token"] > since_token
        ]
        return {"since": since_token, "changes": changes}

    def sync_ack(self, token: str) -> Dict[str, Any]:
        self.store.acknowledge_token(token)
        return {"acknowledged": token}

    def sync_full_export(self, calendar_id: str) -> Dict[str, Any]:
        events = [event for event in self.store.data.get("events", []) if event.get("calendar_id") == calendar_id]
        return {"calendar_id": calendar_id, "events": events}

    def sync_clock(self) -> Dict[str, Any]:
        clock = self.store.bump_clock()
        return {"clock": clock, "timestamp": CalendarStore.utc_now()}

    # Import / export -----------------------------------------------------
    def import_ics_url(self, calendar_id: str, url: str) -> Dict[str, Any]:
        def _record(state: Dict[str, Any]) -> Dict[str, Any]:
            record = {"calendar_id": calendar_id, "url": url, "timestamp": CalendarStore.utc_now()}
            state.setdefault("imports", []).append(record)
            return record

        record = self.store.mutate(_record)
        self.store.record_audit("import.ics_url", metadata={"calendar_id": calendar_id, "url": url})
        return record

    def import_csv(self, calendar_id: str, file_id: str) -> Dict[str, Any]:
        def _record(state: Dict[str, Any]) -> Dict[str, Any]:
            record = {"calendar_id": calendar_id, "file_id": file_id, "timestamp": CalendarStore.utc_now()}
            state.setdefault("imports", []).append(record)
            return record

        record = self.store.mutate(_record)
        self.store.record_audit("import.csv", metadata={"calendar_id": calendar_id, "file_id": file_id})
        return record

    def export_range(self, calendar_id: str, start: str, end: str) -> Dict[str, Any]:
        start_day = _parse_date(start)
        end_day = _parse_date(end)
        events = self.event_list_between(calendar_id, start_day, end_day)
        payload = {"calendar_id": calendar_id, "start": start_day.isoformat(), "end": end_day.isoformat(), "events": events}
        self.store.mutate(lambda state: state.setdefault("exports", []).append({"type": "range", **payload}))
        self.store.record_audit("export.range", metadata={"calendar_id": calendar_id, "start": start, "end": end})
        return payload

    def export_month(self, calendar_id: str, year: int, month: int) -> Dict[str, Any]:
        events = self.event_list_month(calendar_id, year, month)
        payload = {"calendar_id": calendar_id, "year": year, "month": month, "events": events}
        self.store.mutate(lambda state: state.setdefault("exports", []).append({"type": "month", **payload}))
        self.store.record_audit("export.month", metadata={"calendar_id": calendar_id, "year": year, "month": month})
        return payload

    def export_single_event(self, event_id: str) -> Dict[str, Any]:
        event = self.event_get(event_id)
        self.store.mutate(lambda state: state.setdefault("exports", []).append({"type": "event", "event": event}))
        self.store.record_audit("export.event", metadata={"event_id": event_id})
        return {"event": event}

    # Audit ---------------------------------------------------------------
    def audit_list_recent(self, limit: int) -> List[Dict[str, Any]]:
        return list(self.store.data.get("audit", [])[-limit:])

    def audit_get(self, audit_id: str) -> Dict[str, Any]:
        for entry in self.store.data.get("audit", []):
            if entry.get("id") == audit_id:
                return entry
        raise ValueError(f"Audit {audit_id} not found")

    def audit_list_for_event(self, event_id: str) -> List[Dict[str, Any]]:
        return [entry for entry in self.store.data.get("audit", []) if entry.get("metadata", {}).get("event_id") == event_id]

    def audit_list_for_calendar(self, calendar_id: str) -> List[Dict[str, Any]]:
        return [
            entry
            for entry in self.store.data.get("audit", [])
            if entry.get("metadata", {}).get("calendar_id") == calendar_id
        ]

    def audit_export_range(self, start: str, end: str) -> Dict[str, Any]:
        start_dt = _parse_datetime(start)
        end_dt = _parse_datetime(end)
        entries = [
            entry
            for entry in self.store.data.get("audit", [])
            if start_dt.isoformat() <= entry.get("timestamp", "") <= end_dt.isoformat()
        ]
        return {"start": start, "end": end, "entries": entries}

    # Health --------------------------------------------------------------
    def health_ping(self) -> Dict[str, Any]:
        return {"ok": True, "timestamp": CalendarStore.utc_now()}

    def health_version(self) -> Dict[str, Any]:
        return {"name": "calm-chimp", "version": "1.0"}

    def health_migrations(self) -> Dict[str, Any]:
        return {"applied": [], "pending": []}

    def metrics_usage_today(self) -> Dict[str, Any]:
        today = date.today().isoformat()
        events = [event for event in self.store.data.get("events", []) if event.get("start", "").startswith(today)]
        return {"date": today, "events": len(events)}

    # Notifications -------------------------------------------------------
    def notify_subscribe(self, topic: str) -> Dict[str, Any]:
        def _subscribe(state: Dict[str, Any]) -> Dict[str, Any]:
            state.setdefault("subscriptions", [])
            if topic not in state["subscriptions"]:
                state["subscriptions"].append(topic)
            return {"topic": topic}

        result = self.store.mutate(_subscribe)
        self.store.record_audit("notify.subscribe", metadata={"topic": topic})
        return result

    def notify_unsubscribe(self, topic: str) -> Dict[str, Any]:
        def _unsubscribe(state: Dict[str, Any]) -> Dict[str, Any]:
            state.setdefault("subscriptions", [])
            if topic in state["subscriptions"]:
                state["subscriptions"].remove(topic)
            return {"topic": topic}

        result = self.store.mutate(_unsubscribe)
        self.store.record_audit("notify.unsubscribe", metadata={"topic": topic})
        return result

    def notify_list(self) -> Dict[str, Any]:
        return {"topics": list(self.store.data.get("subscriptions", []))}

    def webhook_create(self, target_url: str) -> Dict[str, Any]:
        def _create(state: Dict[str, Any]) -> Dict[str, Any]:
            webhook_id = self.store.consume_id(state, "webhook")
            webhook = {"id": webhook_id, "url": target_url, "active": True}
            state.setdefault("webhooks", []).append(webhook)
            return webhook

        webhook = self.store.mutate(_create)
        self.store.record_audit("webhook.create", metadata={"webhook_id": webhook["id"]})
        return webhook

    def webhook_test(self, webhook_id: str) -> Dict[str, Any]:
        for webhook in self.store.data.get("webhooks", []):
            if webhook.get("id") == webhook_id:
                return {"webhook_id": webhook_id, "status": "ok"}
        raise ValueError(f"Webhook {webhook_id} not found")

    # Conflicts & duplicates ----------------------------------------------
    def conflict_list(self, calendar_id: str, start: str, end: str) -> List[Dict[str, Any]]:
        start_day = _parse_datetime(start)
        end_day = _parse_datetime(end)
        events = self.event_list_between(calendar_id, start_day.date(), end_day.date())
        conflicts: List[Dict[str, Any]] = []
        for idx, event in enumerate(events):
            start_a = datetime.fromisoformat(event["start"])
            end_a = datetime.fromisoformat(event["end"])
            for other in events[idx + 1 :]:
                start_b = datetime.fromisoformat(other["start"])
                end_b = datetime.fromisoformat(other["end"])
                if start_a < end_b and start_b < end_a:
                    conflicts.append({"event_id": event["id"], "other_event_id": other["id"]})
        return conflicts

    def conflict_resolve_keep_first(self, event_id: str, other_event_id: str) -> Dict[str, Any]:
        self.event_delete(other_event_id)
        return {"kept": event_id, "removed": other_event_id}

    def duplicate_scan_month(self, calendar_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        events = self.event_list_month(calendar_id, year, month)
        duplicates: List[Dict[str, Any]] = []
        seen: Dict[Tuple[str, str], str] = {}
        for event in events:
            key = (event.get("title", ""), event.get("start", ""))
            if key in seen:
                duplicates.append({"event_id": event["id"], "matches": seen[key]})
            else:
                seen[key] = event["id"]
        return duplicates

    # Trash & archive -----------------------------------------------------
    def trash_list_events(self) -> List[Dict[str, Any]]:
        return [event for event in self.store.data.get("events", []) if event.get("deleted")]

    def trash_restore_event(self, event_id: str) -> Dict[str, Any]:
        return self.event_restore(event_id)

    def trash_empty(self) -> Dict[str, Any]:
        def _empty(state: Dict[str, Any]) -> Dict[str, Any]:
            state["events"] = [event for event in state.get("events", []) if not event.get("deleted")]
            state["trash"] = [item for item in state.get("trash", []) if item.get("type") != "event"]
            return {"cleared": True}

        result = self.store.mutate(_empty)
        self.store.record_audit("trash.empty", metadata={})
        return result

    def archive_calendar(self, calendar_id: str) -> Dict[str, Any]:
        return self.calendar_update(calendar_id, {"archived": True})

    # Query helpers -------------------------------------------------------
    def query_week_of_month(self, year: int, month: int, week_index: int) -> Dict[str, Any]:
        first_day = date(year, month, 1)
        start = first_day + timedelta(days=7 * week_index)
        end = start + timedelta(days=6)
        return {"start": start.isoformat(), "end": end.isoformat(), "days": [day.isoformat() for day in _date_range(start, end)]}

    def query_list_week_by_index(self, calendar_id: str, year: int, month: int, index: int) -> List[Dict[str, Any]]:
        bounds = self.query_week_of_month(year, month, index)
        start = _parse_date(bounds["start"])
        end = _parse_date(bounds["end"])
        return self.event_list_between(calendar_id, start, end)

    def query_list_first_week_next_month(self, calendar_id: str) -> List[Dict[str, Any]]:
        today = date.today()
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        return self.query_list_week_by_index(calendar_id, year, month, 0)

    def query_list_second_week_next_month(self, calendar_id: str) -> List[Dict[str, Any]]:
        today = date.today()
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        return self.query_list_week_by_index(calendar_id, year, month, 1)

    def query_list_first_week_this_month(self, calendar_id: str) -> List[Dict[str, Any]]:
        today = date.today()
        return self.query_list_week_by_index(calendar_id, today.year, today.month, 0)

    def query_list_weekends_month(self, calendar_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        events = self.event_list_month(calendar_id, year, month)
        weekends = []
        for event in events:
            start_dt = datetime.fromisoformat(event["start"])
            if start_dt.weekday() >= 5:
                weekends.append(event)
        return weekends

    def query_list_weekdays_month(self, calendar_id: str, year: int, month: int) -> List[Dict[str, Any]]:
        events = self.event_list_month(calendar_id, year, month)
        weekdays = []
        for event in events:
            start_dt = datetime.fromisoformat(event["start"])
            if start_dt.weekday() < 5:
                weekdays.append(event)
        return weekdays

    def query_count_busy_in_week(self, calendar_id: str, week_start: str) -> Dict[str, Any]:
        week_day = _parse_date(week_start)
        events = self.event_list_week(calendar_id, week_day)
        busy_minutes = 0
        for event in events:
            start_dt = datetime.fromisoformat(event["start"])
            end_dt = datetime.fromisoformat(event["end"])
            busy_minutes += int((end_dt - start_dt).total_seconds() // 60)
        return {"calendar_id": calendar_id, "week_start": week_day.isoformat(), "busy_minutes": busy_minutes}


SERVICE = CalendarService()


def _register_tool(
    name: str,
    description: str,
    args: List[Tuple[str, Any] | Tuple[str, Any, Any]],
    handler: Callable[..., Any],
    *,
    category: str,
    tags: Tuple[str, ...] = (),
) -> None:
    from inspect import Parameter, Signature

    parameters = []
    annotations: Dict[str, Any] = {}
    for entry in args:
        if len(entry) == 3:
            arg_name, annotation, default_value = entry
        else:
            arg_name, annotation = entry  # type: ignore[misc]
            default_value = Parameter.empty
        annotations[arg_name] = annotation
        parameters.append(
            Parameter(
                arg_name,
                Parameter.POSITIONAL_OR_KEYWORD,
                annotation=annotation,
                default=default_value,
            )
        )
    signature = Signature(parameters)

    def _tool_wrapper(**kwargs: Any) -> Any:
        return handler(**kwargs)

    _tool_wrapper.__name__ = name.replace(".", "_")
    _tool_wrapper.__signature__ = signature
    annotations["return"] = Any
    _tool_wrapper.__annotations__ = annotations
    register_api(name, description=description, category=category, tags=tags)(_tool_wrapper)


# Calendar tools
_register_tool(
    "calendar.create",
    "Create a calendar with a simple name.",
    [("name", str)],
    lambda name: SERVICE.calendar_create(name),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.get",
    "Fetch a calendar by id.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.calendar_get(calendar_id),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.list",
    "List calendars.",
    [],
    lambda: SERVICE.calendar_list(),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.rename",
    "Rename a calendar.",
    [("calendar_id", str), ("name", str)],
    lambda calendar_id, name: SERVICE.calendar_update(calendar_id, {"name": name}),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.color_set",
    "Assign a display color to a calendar.",
    [("calendar_id", str), ("color", str)],
    lambda calendar_id, color: SERVICE.calendar_update(calendar_id, {"color": color}),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.set_default",
    "Mark a calendar as the default.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.calendar_set_default(calendar_id),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.timezone_set",
    "Set the timezone for a calendar.",
    [("calendar_id", str), ("tz", str)],
    lambda calendar_id, tz: SERVICE.calendar_update(calendar_id, {"timezone": tz}),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.copy",
    "Copy a calendar and its events.",
    [("calendar_id", str), ("name", str)],
    lambda calendar_id, name: SERVICE.calendar_copy(calendar_id, name),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.delete",
    "Soft-delete a calendar.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.calendar_delete(calendar_id),
    category="calendar",
    tags=("calendar",),
)
_register_tool(
    "calendar.restore",
    "Restore a calendar from trash.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.calendar_restore(calendar_id),
    category="calendar",
    tags=("calendar",),
)

# Event tools
_register_tool(
    "event.create",
    "Create a timed event.",
    [("calendar_id", str), ("title", str), ("start", str), ("end", str)],
    lambda calendar_id, title, start, end: SERVICE.event_create(calendar_id, title, start, end),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.create_all_day",
    "Create an all-day event.",
    [("calendar_id", str), ("title", str), ("date", str)],
    lambda calendar_id, title, date: SERVICE.event_create_all_day(calendar_id, title, date),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.get",
    "Fetch a single event.",
    [("event_id", str)],
    lambda event_id: SERVICE.event_get(event_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.update_title",
    "Update the event title.",
    [("event_id", str), ("title", str)],
    lambda event_id, title: SERVICE.event_update_fields(event_id, {"title": title}),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.update_time",
    "Update start and end times.",
    [("event_id", str), ("start", str), ("end", str)],
    lambda event_id, start, end: SERVICE.event_update_fields(event_id, {"start": start, "end": end}),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.update_description",
    "Update the event description.",
    [("event_id", str), ("description", str)],
    lambda event_id, description: SERVICE.event_update_fields(event_id, {"description": description}),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.set_status",
    "Change event status.",
    [("event_id", str), ("status", str)],
    lambda event_id, status: SERVICE.event_update_fields(event_id, {"status": status}),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.set_transparency",
    "Change transparency (busy/free).",
    [("event_id", str), ("busy_free", str)],
    lambda event_id, busy_free: SERVICE.event_update_fields(event_id, {"transparency": busy_free}),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.move",
    "Move event to another calendar.",
    [("event_id", str), ("target_calendar_id", str)],
    lambda event_id, target_calendar_id: SERVICE.event_move(event_id, target_calendar_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.duplicate",
    "Duplicate an event.",
    [("event_id", str), ("target_calendar_id", str)],
    lambda event_id, target_calendar_id: SERVICE.event_duplicate(event_id, target_calendar_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.cancel",
    "Cancel an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.event_cancel(event_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.delete",
    "Delete an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.event_delete(event_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.restore",
    "Restore a deleted event.",
    [("event_id", str)],
    lambda event_id: SERVICE.event_restore(event_id),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.set_color",
    "Set a display color for an event.",
    [("event_id", str), ("color", str)],
    lambda event_id, color: SERVICE.event_set_color(event_id, color),
    category="event",
    tags=("event", "color"),
)
_register_tool(
    "event.list_today",
    "List today's events for a calendar.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.event_list_day(calendar_id, date.today()),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.list_tomorrow",
    "List tomorrow's events for a calendar.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.event_list_day(calendar_id, date.today() + timedelta(days=1)),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.list_day",
    "List events for a specific day.",
    [("calendar_id", str), ("date", str)],
    lambda calendar_id, date: SERVICE.event_list_day(calendar_id, _parse_date(date)),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.list_week",
    "List events for a calendar week.",
    [("calendar_id", str), ("week_start", str)],
    lambda calendar_id, week_start: SERVICE.event_list_week(calendar_id, _parse_date(week_start)),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.list_month",
    "List events for a month.",
    [("calendar_id", str), ("year", int), ("month", int)],
    lambda calendar_id, year, month: SERVICE.event_list_month(calendar_id, year, month),
    category="event",
    tags=("event",),
)
_register_tool(
    "event.quick_add",
    "Quickly create an event using sensible defaults.",
    [
        ("title", str),
        ("date_text", str),
        ("time_text", Optional[str], None),
        ("calendar_id", Optional[str], None),
        ("duration_minutes", int, 60),
        ("notes", Optional[str], None),
        ("attendees", Optional[List[str]], None),
    ],
    lambda title, date_text, time_text=None, calendar_id=None, duration_minutes=60, notes=None, attendees=None: SERVICE.event_quick_add(
        title=title,
        date_text=date_text,
        time_text=time_text,
        calendar_id=calendar_id,
        duration_minutes=duration_minutes,
        notes=notes,
        attendees=attendees,
    ),
    category="event",
    tags=("event", "quick"),
)

# Recurrence tools
_register_tool(
    "recur.set_daily",
    "Set a daily recurrence.",
    [("event_id", str)],
    lambda event_id: SERVICE.recurrence_update(event_id, {"frequency": "daily"}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_weekly",
    "Set a weekly recurrence.",
    [("event_id", str)],
    lambda event_id: SERVICE.recurrence_update(event_id, {"frequency": "weekly"}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_monthly_by_date",
    "Set monthly recurrence by calendar day.",
    [("event_id", str), ("day", int)],
    lambda event_id, day: SERVICE.recurrence_update(event_id, {"frequency": "monthly", "day": day}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_monthly_by_weekday",
    "Set monthly recurrence by weekday and ordinal.",
    [("event_id", str), ("weekday", str), ("ordinal", int)],
    lambda event_id, weekday, ordinal: SERVICE.recurrence_update(
        event_id,
        {"frequency": "monthly", "weekday": weekday, "ordinal": ordinal},
    ),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_yearly",
    "Set yearly recurrence.",
    [("event_id", str), ("month", int), ("day", int)],
    lambda event_id, month, day: SERVICE.recurrence_update(event_id, {"frequency": "yearly", "month": month, "day": day}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_ends_on",
    "Stop recurrence on a date.",
    [("event_id", str), ("date", str)],
    lambda event_id, date: SERVICE.recurrence_update(event_id, {"ends_on": date}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.set_ends_after",
    "Stop recurrence after a count.",
    [("event_id", str), ("count", int)],
    lambda event_id, count: SERVICE.recurrence_update(event_id, {"ends_after": count}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.pause",
    "Pause recurrence.",
    [("event_id", str)],
    lambda event_id: SERVICE.recurrence_update(event_id, {"paused": True}),
    category="recurrence",
    tags=("recurrence",),
)
_register_tool(
    "recur.clear",
    "Clear recurrence settings.",
    [("event_id", str)],
    lambda event_id: SERVICE.recurrence_clear(event_id),
    category="recurrence",
    tags=("recurrence",),
)

# Instance overrides
_register_tool(
    "instance.list",
    "List overrides for a recurring series.",
    [("series_id", str), ("start", str), ("end", str)],
    lambda series_id, start, end: SERVICE.instance_list(series_id, start, end),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.get",
    "Get a specific occurrence override.",
    [("series_id", str), ("occurrence_date", str)],
    lambda series_id, occurrence_date: SERVICE.instance_get(series_id, occurrence_date),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.update_time",
    "Override time for an occurrence.",
    [("series_id", str), ("occurrence_date", str), ("start", str), ("end", str)],
    lambda series_id, occurrence_date, start, end: SERVICE.instance_update(
        series_id,
        occurrence_date,
        {"start": start, "end": end},
    ),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.update_title",
    "Override title for an occurrence.",
    [("series_id", str), ("occurrence_date", str), ("title", str)],
    lambda series_id, occurrence_date, title: SERVICE.instance_update(
        series_id,
        occurrence_date,
        {"title": title},
    ),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.cancel",
    "Cancel a single occurrence.",
    [("series_id", str), ("occurrence_date", str)],
    lambda series_id, occurrence_date: SERVICE.instance_cancel(series_id, occurrence_date),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.skip",
    "Skip a single occurrence.",
    [("series_id", str), ("occurrence_date", str)],
    lambda series_id, occurrence_date: SERVICE.instance_skip(series_id, occurrence_date),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.detach_to_event",
    "Detach an override into a standalone event.",
    [("series_id", str), ("occurrence_date", str)],
    lambda series_id, occurrence_date: SERVICE.instance_detach(series_id, occurrence_date),
    category="instance",
    tags=("instance",),
)
_register_tool(
    "instance.restore",
    "Remove an override for a date.",
    [("series_id", str), ("occurrence_date", str)],
    lambda series_id, occurrence_date: SERVICE.instance_restore(series_id, occurrence_date),
    category="instance",
    tags=("instance",),
)

# Attendees
_register_tool(
    "attendee.add",
    "Add a required attendee.",
    [("event_id", str), ("email", str)],
    lambda event_id, email: SERVICE.attendee_add(event_id, email, optional=False),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.add_optional",
    "Add an optional attendee.",
    [("event_id", str), ("email", str)],
    lambda event_id, email: SERVICE.attendee_add(event_id, email, optional=True),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.remove",
    "Remove an attendee.",
    [("event_id", str), ("email", str)],
    lambda event_id, email: SERVICE.attendee_remove(event_id, email),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.list",
    "List attendees for an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.attendee_list(event_id),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.set_response",
    "Update response status.",
    [("event_id", str), ("email", str), ("response", str)],
    lambda event_id, email, response: SERVICE.attendee_set(event_id, email, {"response": response}),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.set_role",
    "Update attendee role.",
    [("event_id", str), ("email", str), ("role", str)],
    lambda event_id, email, role: SERVICE.attendee_set(event_id, email, {"role": role}),
    category="attendee",
    tags=("attendee",),
)
_register_tool(
    "attendee.set_name",
    "Set attendee display name.",
    [("event_id", str), ("email", str), ("name", str)],
    lambda event_id, email, name: SERVICE.attendee_set(event_id, email, {"name": name}),
    category="attendee",
    tags=("attendee",),
)

# Reminders
_register_tool(
    "reminder.add_minutes_before",
    "Add a reminder before the event.",
    [("event_id", str), ("minutes", int)],
    lambda event_id, minutes: SERVICE.reminder_add(event_id, minutes),
    category="reminder",
    tags=("reminder",),
)
_register_tool(
    "reminder.remove",
    "Remove a reminder.",
    [("event_id", str), ("minutes", int)],
    lambda event_id, minutes: SERVICE.reminder_remove(event_id, minutes),
    category="reminder",
    tags=("reminder",),
)
_register_tool(
    "reminder.list",
    "List event reminders.",
    [("event_id", str)],
    lambda event_id: SERVICE.reminder_list(event_id),
    category="reminder",
    tags=("reminder",),
)
_register_tool(
    "reminder.clear",
    "Clear reminders for an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.reminder_clear(event_id),
    category="reminder",
    tags=("reminder",),
)
_register_tool(
    "reminder.set_default",
    "Set default reminders for a calendar.",
    [("calendar_id", str), ("minutes", int)],
    lambda calendar_id, minutes: SERVICE.reminder_set_default(calendar_id, minutes),
    category="reminder",
    tags=("reminder",),
)
_register_tool(
    "reminder.snooze",
    "Snooze reminders for an event.",
    [("event_id", str), ("minutes", int)],
    lambda event_id, minutes: SERVICE.reminder_snooze(event_id, minutes),
    category="reminder",
    tags=("reminder",),
)

# Availability
_register_tool(
    "avail.free_busy_day",
    "Return busy blocks for a day.",
    [("calendar_id", str), ("date", str)],
    lambda calendar_id, date: SERVICE.availability_free_busy(calendar_id, _parse_date(date), _parse_date(date)),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.free_busy_week",
    "Busy timeline for a week.",
    [("calendar_id", str), ("week_start", str)],
    lambda calendar_id, week_start: SERVICE.availability_free_busy(
        calendar_id,
        _parse_date(week_start),
        _parse_date(week_start) + timedelta(days=6),
    ),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.free_busy_range",
    "Busy timeline for a custom range.",
    [("calendar_id", str), ("start", str), ("end", str)],
    lambda calendar_id, start, end: SERVICE.availability_free_busy(
        calendar_id,
        _parse_datetime(start).date(),
        _parse_datetime(end).date(),
    ),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.next_free_block",
    "Find the next free block of minutes.",
    [("calendar_id", str), ("minutes", int)],
    lambda calendar_id, minutes: SERVICE.availability_next_free_block(calendar_id, minutes),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.find_slot_on_day",
    "Find a slot on a day.",
    [("calendar_id", str), ("date", str), ("minutes", int)],
    lambda calendar_id, date, minutes: SERVICE.availability_find_slot_on_day(calendar_id, _parse_date(date), minutes),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.find_slot_in_week",
    "Find a slot within a week.",
    [("calendar_id", str), ("week_start", str), ("minutes", int)],
    lambda calendar_id, week_start, minutes: SERVICE.availability_find_slot_in_week(calendar_id, _parse_date(week_start), minutes),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.meeting_suggest",
    "Suggest a meeting slot on a day.",
    [("calendar_id", str), ("date", str), ("minutes", int)],
    lambda calendar_id, date, minutes: SERVICE.availability_meeting_suggest(calendar_id, _parse_date(date), minutes),
    category="availability",
    tags=("availability",),
)
_register_tool(
    "avail.busy_summary_day",
    "Summarize busy minutes for a day.",
    [("calendar_id", str), ("date", str)],
    lambda calendar_id, date: SERVICE.availability_busy_summary(calendar_id, _parse_date(date)),
    category="availability",
    tags=("availability",),
)

# Focus tools
_register_tool(
    "focus.create_block",
    "Create a focus block event.",
    [("calendar_id", str), ("title", str), ("date", str), ("minutes", int)],
    lambda calendar_id, title, date, minutes: SERVICE.focus_create_block(calendar_id, title, date, minutes),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.auto_plan_week",
    "Suggest focus blocks for a week.",
    [("calendar_id", str), ("week_start", str)],
    lambda calendar_id, week_start: SERVICE.focus_auto_plan_week(calendar_id, week_start),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.auto_plan_until",
    "Suggest focus blocks until a date.",
    [("calendar_id", str), ("date", str)],
    lambda calendar_id, date: SERVICE.focus_auto_plan_until(calendar_id, date),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.lock_block",
    "Lock a focus event.",
    [("event_id", str)],
    lambda event_id: SERVICE.focus_lock(event_id),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.unlock_block",
    "Unlock a focus event.",
    [("event_id", str)],
    lambda event_id: SERVICE.focus_unlock(event_id),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.defer_block_by_days",
    "Defer a focus block by days.",
    [("event_id", str), ("days", int)],
    lambda event_id, days: SERVICE.focus_defer(event_id, days),
    category="focus",
    tags=("focus",),
)
_register_tool(
    "focus.bump_to_tomorrow",
    "Move a focus block to tomorrow.",
    [("event_id", str)],
    lambda event_id: SERVICE.focus_bump(event_id),
    category="focus",
    tags=("focus",),
)

# Templates
_register_tool(
    "template.create",
    "Create a template.",
    [("name", str), ("minutes", int)],
    lambda name, minutes: SERVICE.template_create(name, minutes),
    category="template",
    tags=("template",),
)
_register_tool(
    "template.get",
    "Fetch a template.",
    [("template_id", str)],
    lambda template_id: SERVICE.template_get(template_id),
    category="template",
    tags=("template",),
)
_register_tool(
    "template.list",
    "List templates.",
    [],
    lambda: SERVICE.template_list(),
    category="template",
    tags=("template",),
)
_register_tool(
    "template.rename",
    "Rename a template.",
    [("template_id", str), ("name", str)],
    lambda template_id, name: SERVICE.template_rename(template_id, name),
    category="template",
    tags=("template",),
)
_register_tool(
    "template.instantiate",
    "Create an event from a template.",
    [("template_id", str), ("calendar_id", str), ("date", str)],
    lambda template_id, calendar_id, date: SERVICE.template_instantiate(template_id, calendar_id, date),
    category="template",
    tags=("template",),
)

# Tags
_register_tool(
    "tag.create",
    "Create a tag.",
    [("name", str)],
    lambda name: SERVICE.tag_create(name),
    category="tag",
    tags=("tag",),
)
_register_tool(
    "tag.list",
    "List tags.",
    [],
    lambda: SERVICE.tag_list(),
    category="tag",
    tags=("tag",),
)
_register_tool(
    "tag.rename",
    "Rename a tag.",
    [("tag_id", str), ("name", str)],
    lambda tag_id, name: SERVICE.tag_rename(tag_id, name),
    category="tag",
    tags=("tag",),
)
_register_tool(
    "tag.delete",
    "Delete a tag.",
    [("tag_id", str)],
    lambda tag_id: SERVICE.tag_delete(tag_id),
    category="tag",
    tags=("tag",),
)
_register_tool(
    "tag.add_to_event",
    "Attach a tag to an event.",
    [("event_id", str), ("tag_id", str)],
    lambda event_id, tag_id: SERVICE.tag_add_to_event(event_id, tag_id),
    category="tag",
    tags=("tag",),
)
_register_tool(
    "tag.remove_from_event",
    "Detach a tag from an event.",
    [("event_id", str), ("tag_id", str)],
    lambda event_id, tag_id: SERVICE.tag_remove_from_event(event_id, tag_id),
    category="tag",
    tags=("tag",),
)

# Locations
_register_tool(
    "location.set_text",
    "Set event location text.",
    [("event_id", str), ("text", str)],
    lambda event_id, text: SERVICE.location_set_text(event_id, text),
    category="location",
    tags=("location",),
)
_register_tool(
    "location.set_coordinates",
    "Set event location coordinates.",
    [("event_id", str), ("lat", float), ("lon", float)],
    lambda event_id, lat, lon: SERVICE.location_set_coordinates(event_id, lat, lon),
    category="location",
    tags=("location",),
)
_register_tool(
    "location.get",
    "Get event location.",
    [("event_id", str)],
    lambda event_id: SERVICE.location_get(event_id),
    category="location",
    tags=("location",),
)
_register_tool(
    "location.clear",
    "Clear event location.",
    [("event_id", str)],
    lambda event_id: SERVICE.location_clear(event_id),
    category="location",
    tags=("location",),
)

# Attachments
_register_tool(
    "attachment.add_url",
    "Attach a URL to an event.",
    [("event_id", str), ("url", str)],
    lambda event_id, url: SERVICE.attachment_add_url(event_id, url),
    category="attachment",
    tags=("attachment",),
)
_register_tool(
    "attachment.add_file_ref",
    "Attach a file reference to an event.",
    [("event_id", str), ("file_id", str)],
    lambda event_id, file_id: SERVICE.attachment_add_file_ref(event_id, file_id),
    category="attachment",
    tags=("attachment",),
)
_register_tool(
    "attachment.list",
    "List event attachments.",
    [("event_id", str)],
    lambda event_id: SERVICE.attachment_list(event_id),
    category="attachment",
    tags=("attachment",),
)
_register_tool(
    "attachment.remove",
    "Remove an attachment by id.",
    [("event_id", str), ("ref", str)],
    lambda event_id, ref: SERVICE.attachment_remove(event_id, ref),
    category="attachment",
    tags=("attachment",),
)
_register_tool(
    "attachment.clear",
    "Clear attachments from an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.attachment_clear(event_id),
    category="attachment",
    tags=("attachment",),
)

# Notes and checklists
_register_tool(
    "note.add",
    "Add a note to an event.",
    [("event_id", str), ("text", str)],
    lambda event_id, text: SERVICE.note_add(event_id, text),
    category="note",
    tags=("note",),
)
_register_tool(
    "note.list",
    "List event notes.",
    [("event_id", str)],
    lambda event_id: SERVICE.note_list(event_id),
    category="note",
    tags=("note",),
)
_register_tool(
    "note.update",
    "Update a note's text.",
    [("note_id", str), ("text", str)],
    lambda note_id, text: SERVICE.note_update(note_id, text),
    category="note",
    tags=("note",),
)
_register_tool(
    "note.remove",
    "Remove a note.",
    [("note_id", str)],
    lambda note_id: SERVICE.note_remove(note_id),
    category="note",
    tags=("note",),
)
_register_tool(
    "checklist.toggle_item",
    "Toggle a checklist item on an event.",
    [("event_id", str), ("item_id", str)],
    lambda event_id, item_id: SERVICE.checklist_toggle(event_id, item_id),
    category="note",
    tags=("checklist",),
)

# Preferences
_register_tool(
    "prefs.get",
    "Get calendar preferences.",
    [],
    lambda: SERVICE.prefs_get(),
    category="prefs",
    tags=("prefs",),
)
_register_tool(
    "prefs.set_timezone",
    "Set default timezone.",
    [("tz", str)],
    lambda tz: SERVICE.prefs_set({"timezone": tz}),
    category="prefs",
    tags=("prefs",),
)
_register_tool(
    "prefs.set_week_start",
    "Set week start day.",
    [("dow", str)],
    lambda dow: SERVICE.prefs_set({"week_start": dow}),
    category="prefs",
    tags=("prefs",),
)
_register_tool(
    "prefs.set_default_calendar",
    "Set the default calendar id.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.prefs_set({"default_calendar_id": calendar_id}),
    category="prefs",
    tags=("prefs",),
)
_register_tool(
    "prefs.set_work_hours",
    "Set work hours.",
    [("start", str), ("end", str)],
    lambda start, end: SERVICE.prefs_set({"work_hours": {"start": start, "end": end}}),
    category="prefs",
    tags=("prefs",),
)
_register_tool(
    "prefs.set_default_duration",
    "Set default event duration in minutes.",
    [("minutes", int)],
    lambda minutes: SERVICE.prefs_set({"default_duration": minutes}),
    category="prefs",
    tags=("prefs",),
)

# Sharing / ACL
_register_tool(
    "acl.add",
    "Add a calendar share entry.",
    [("calendar_id", str), ("email", str), ("role", str)],
    lambda calendar_id, email, role: SERVICE.acl_add(calendar_id, email, role),
    category="acl",
    tags=("acl",),
)
_register_tool(
    "acl.remove",
    "Remove an ACL entry.",
    [("calendar_id", str), ("email", str)],
    lambda calendar_id, email: SERVICE.acl_remove(calendar_id, email),
    category="acl",
    tags=("acl",),
)
_register_tool(
    "acl.list",
    "List ACL entries.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.acl_list(calendar_id),
    category="acl",
    tags=("acl",),
)
_register_tool(
    "acl.set_role",
    "Update ACL role.",
    [("calendar_id", str), ("email", str), ("role", str)],
    lambda calendar_id, email, role: SERVICE.acl_set_role(calendar_id, email, role),
    category="acl",
    tags=("acl",),
)
_register_tool(
    "acl.publish_ics",
    "Toggle public ICS feed.",
    [("calendar_id", str), ("enabled", bool)],
    lambda calendar_id, enabled: SERVICE.acl_publish_ics(calendar_id, enabled),
    category="acl",
    tags=("acl",),
)
_register_tool(
    "acl.set_privacy_busy_only",
    "Toggle busy-only privacy.",
    [("calendar_id", str), ("enabled", bool)],
    lambda calendar_id, enabled: SERVICE.acl_set_privacy(calendar_id, enabled),
    category="acl",
    tags=("acl",),
)

# Sync
_register_tool(
    "sync.delta_token_new",
    "Create a new sync token.",
    [],
    lambda: SERVICE.sync_delta_token_new(),
    category="sync",
    tags=("sync",),
)
_register_tool(
    "sync.pull_changes",
    "Pull changes since a token.",
    [("since_token", str)],
    lambda since_token: SERVICE.sync_pull_changes(since_token),
    category="sync",
    tags=("sync",),
)
_register_tool(
    "sync.ack",
    "Acknowledge a sync token.",
    [("token", str)],
    lambda token: SERVICE.sync_ack(token),
    category="sync",
    tags=("sync",),
)
_register_tool(
    "sync.full_export",
    "Export calendar contents.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.sync_full_export(calendar_id),
    category="sync",
    tags=("sync",),
)
_register_tool(
    "sync.clock",
    "Get sync clock.",
    [],
    lambda: SERVICE.sync_clock(),
    category="sync",
    tags=("sync",),
)

# Import / export
_register_tool(
    "import.ics_url",
    "Import events from an ICS feed URL.",
    [("calendar_id", str), ("url", str)],
    lambda calendar_id, url: SERVICE.import_ics_url(calendar_id, url),
    category="import",
    tags=("import",),
)
_register_tool(
    "import.csv",
    "Import events from a CSV file id.",
    [("calendar_id", str), ("file_id", str)],
    lambda calendar_id, file_id: SERVICE.import_csv(calendar_id, file_id),
    category="import",
    tags=("import",),
)
_register_tool(
    "export.ics_range",
    "Export events between dates.",
    [("calendar_id", str), ("start", str), ("end", str)],
    lambda calendar_id, start, end: SERVICE.export_range(calendar_id, start, end),
    category="export",
    tags=("export",),
)
_register_tool(
    "export.ics_month",
    "Export events for a month.",
    [("calendar_id", str), ("year", int), ("month", int)],
    lambda calendar_id, year, month: SERVICE.export_month(calendar_id, year, month),
    category="export",
    tags=("export",),
)
_register_tool(
    "export.single_event",
    "Export a single event.",
    [("event_id", str)],
    lambda event_id: SERVICE.export_single_event(event_id),
    category="export",
    tags=("export",),
)

# Audit / history
_register_tool(
    "audit.list_recent",
    "List recent audit entries.",
    [("limit", int)],
    lambda limit: SERVICE.audit_list_recent(limit),
    category="audit",
    tags=("audit",),
)
_register_tool(
    "audit.get",
    "Fetch a single audit entry.",
    [("audit_id", str)],
    lambda audit_id: SERVICE.audit_get(audit_id),
    category="audit",
    tags=("audit",),
)
_register_tool(
    "audit.list_for_event",
    "List audit entries for an event.",
    [("event_id", str)],
    lambda event_id: SERVICE.audit_list_for_event(event_id),
    category="audit",
    tags=("audit",),
)
_register_tool(
    "audit.list_for_calendar",
    "List audit entries for a calendar.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.audit_list_for_calendar(calendar_id),
    category="audit",
    tags=("audit",),
)
_register_tool(
    "audit.export_range",
    "Export audit entries between datetimes.",
    [("start", str), ("end", str)],
    lambda start, end: SERVICE.audit_export_range(start, end),
    category="audit",
    tags=("audit",),
)

# Health / metrics
_register_tool(
    "health.ping",
    "Simple health check.",
    [],
    lambda: SERVICE.health_ping(),
    category="health",
    tags=("health",),
)
_register_tool(
    "health.version",
    "Return version info.",
    [],
    lambda: SERVICE.health_version(),
    category="health",
    tags=("health",),
)
_register_tool(
    "health.migrations",
    "Show migration status.",
    [],
    lambda: SERVICE.health_migrations(),
    category="health",
    tags=("health",),
)
_register_tool(
    "metrics.usage_today",
    "Show simple usage metrics for today.",
    [],
    lambda: SERVICE.metrics_usage_today(),
    category="metrics",
    tags=("metrics",),
)

# Notifications / webhooks
_register_tool(
    "notify.subscribe",
    "Subscribe to a topic.",
    [("topic", str)],
    lambda topic: SERVICE.notify_subscribe(topic),
    category="notify",
    tags=("notify",),
)
_register_tool(
    "notify.unsubscribe",
    "Unsubscribe from a topic.",
    [("topic", str)],
    lambda topic: SERVICE.notify_unsubscribe(topic),
    category="notify",
    tags=("notify",),
)
_register_tool(
    "notify.list",
    "List notification topics.",
    [],
    lambda: SERVICE.notify_list(),
    category="notify",
    tags=("notify",),
)
_register_tool(
    "webhook.create",
    "Create a webhook subscription.",
    [("target_url", str)],
    lambda target_url: SERVICE.webhook_create(target_url),
    category="notify",
    tags=("webhook",),
)
_register_tool(
    "webhook.test",
    "Test a webhook id.",
    [("webhook_id", str)],
    lambda webhook_id: SERVICE.webhook_test(webhook_id),
    category="notify",
    tags=("webhook",),
)

# Conflicts / duplicates
_register_tool(
    "conflict.list_for_range",
    "List conflicting events in a range.",
    [("calendar_id", str), ("start", str), ("end", str)],
    lambda calendar_id, start, end: SERVICE.conflict_list(calendar_id, start, end),
    category="conflict",
    tags=("conflict",),
)
_register_tool(
    "conflict.resolve_keep_first",
    "Resolve a conflict by keeping the first event.",
    [("event_id", str), ("other_event_id", str)],
    lambda event_id, other_event_id: SERVICE.conflict_resolve_keep_first(event_id, other_event_id),
    category="conflict",
    tags=("conflict",),
)
_register_tool(
    "duplicate.scan_month",
    "Scan for duplicate events in a month.",
    [("calendar_id", str), ("year", int), ("month", int)],
    lambda calendar_id, year, month: SERVICE.duplicate_scan_month(calendar_id, year, month),
    category="conflict",
    tags=("duplicate",),
)

# Trash / archive
_register_tool(
    "trash.list_events",
    "List trashed events.",
    [],
    lambda: SERVICE.trash_list_events(),
    category="trash",
    tags=("trash",),
)
_register_tool(
    "trash.restore_event",
    "Restore a trashed event.",
    [("event_id", str)],
    lambda event_id: SERVICE.trash_restore_event(event_id),
    category="trash",
    tags=("trash",),
)
_register_tool(
    "trash.empty",
    "Permanently clear trashed events.",
    [],
    lambda: SERVICE.trash_empty(),
    category="trash",
    tags=("trash",),
)
_register_tool(
    "archive.calendar",
    "Archive a calendar.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.archive_calendar(calendar_id),
    category="trash",
    tags=("archive",),
)

# Query helpers
_register_tool(
    "query.week_of_month",
    "Return the date range for a week index.",
    [("year", int), ("month", int), ("week_index", int)],
    lambda year, month, week_index: SERVICE.query_week_of_month(year, month, week_index),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_week_by_index",
    "List events for a week index.",
    [("calendar_id", str), ("year", int), ("month", int), ("index", int)],
    lambda calendar_id, year, month, index: SERVICE.query_list_week_by_index(calendar_id, year, month, index),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_first_week_next_month",
    "List events for the first week of next month.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.query_list_first_week_next_month(calendar_id),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_second_week_next_month",
    "List events for the second week of next month.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.query_list_second_week_next_month(calendar_id),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_first_week_this_month",
    "List events for the first week of this month.",
    [("calendar_id", str)],
    lambda calendar_id: SERVICE.query_list_first_week_this_month(calendar_id),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_weekends_month",
    "List weekend events for a month.",
    [("calendar_id", str), ("year", int), ("month", int)],
    lambda calendar_id, year, month: SERVICE.query_list_weekends_month(calendar_id, year, month),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.list_weekdays_month",
    "List weekday events for a month.",
    [("calendar_id", str), ("year", int), ("month", int)],
    lambda calendar_id, year, month: SERVICE.query_list_weekdays_month(calendar_id, year, month),
    category="query",
    tags=("query",),
)
_register_tool(
    "query.count_busy_in_week",
    "Count busy minutes for a week starting date.",
    [("calendar_id", str), ("week_start", str)],
    lambda calendar_id, week_start: SERVICE.query_count_busy_in_week(calendar_id, week_start),
    category="query",
    tags=("query",),
)
