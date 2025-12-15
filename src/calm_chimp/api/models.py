from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

from ..domain import CalendarEvent, Category


class CategoryPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    name: str
    color: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default=None)
    description: str = Field(default="")

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryPayload":
        return cls(
            id=category.id,
            user_id=category.user_id,
            name=category.name,
            color=category.color,
            icon=category.icon,
            description=category.description,
        )


class EventPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    title: str
    starts_at: str
    ends_at: str
    status: str
    category_id: Optional[str] = Field(default=None)
    category: Optional[CategoryPayload] = Field(default=None)
    notes: str = Field(default="")
    location: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = Field(default=None)
    updated_at: Optional[str] = Field(default=None)

    @classmethod
    def from_domain(cls, event: CalendarEvent) -> "EventPayload":
        return cls(
            id=event.id,
            user_id=event.user_id,
            title=event.title,
            starts_at=_iso(event.starts_at),
            ends_at=_iso(event.ends_at),
            status=event.status.value,
            category_id=event.category_id,
            category=CategoryPayload.from_domain(event.category) if event.category else None,
            notes=event.notes,
            location=event.location,
            metadata=event.metadata,
            created_at=_iso(event.created_at),
            updated_at=_iso(event.updated_at),
        )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None
