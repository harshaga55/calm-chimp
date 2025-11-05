from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from .enums import EventStatus


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"Unsupported datetime value: {value!r}")


@dataclass(slots=True)
class Category:
    id: str
    user_id: str
    name: str
    color: Optional[str] = None
    icon: Optional[str] = None
    description: str = ""

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "Category":
        return cls(
            id=str(record["id"]),
            user_id=str(record["user_id"]),
            name=str(record["name"]),
            color=record.get("color"),
            icon=record.get("icon"),
            description=record.get("description") or "",
        )

    def to_record(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "color": self.color,
            "icon": self.icon,
            "description": self.description,
        }


@dataclass(slots=True)
class CalendarEvent:
    id: str
    user_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    status: EventStatus = EventStatus.PLANNED
    category_id: Optional[str] = None
    category: Optional[Category] = None
    notes: str = ""
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any], *, category: Optional[Dict[str, Any]] = None) -> "CalendarEvent":
        instance = cls(
            id=str(record["id"]),
            user_id=str(record["user_id"]),
            title=str(record["title"]),
            starts_at=_parse_datetime(record["starts_at"]),
            ends_at=_parse_datetime(record["ends_at"]),
            status=EventStatus(record.get("status") or EventStatus.PLANNED),
            category_id=record.get("category_id"),
            notes=record.get("notes") or "",
            location=record.get("location"),
            metadata=dict(record.get("metadata") or {}),
            created_at=_parse_datetime(record["created_at"]) if record.get("created_at") else None,
            updated_at=_parse_datetime(record["updated_at"]) if record.get("updated_at") else None,
        )
        if category:
            instance.category = Category.from_record(category)
        return instance

    def to_record(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "status": self.status.value,
            "category_id": self.category_id,
            "notes": self.notes,
            "location": self.location,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class UserProfile:
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> "UserProfile":
        return cls(
            id=str(record["id"]),
            email=str(record["email"]),
            full_name=record.get("full_name"),
            avatar_url=record.get("avatar_url"),
        )
