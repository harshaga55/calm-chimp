from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


@dataclass
class StudyTask:
    id: str
    subject: str
    title: str
    due_date: date
    estimated_hours: float
    status: str = "pending"
    notes: str = ""
    plan: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "StudyTask":
        return cls(
            id=data["id"],
            subject=data["subject"],
            title=data["title"],
            due_date=datetime.fromisoformat(data["due_date"]).date(),
            estimated_hours=float(data.get("estimated_hours", 1.0)),
            status=data.get("status", "pending"),
            notes=data.get("notes", ""),
            plan=list(data.get("plan", [])),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "title": self.title,
            "due_date": self.due_date.isoformat(),
            "estimated_hours": self.estimated_hours,
            "status": self.status,
            "notes": self.notes,
            "plan": self.plan,
        }


@dataclass
class StudySubject:
    name: str
    description: str = ""
    color: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "StudySubject":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            color=data.get("color"),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "color": self.color,
        }


@dataclass
class HistoryEntry:
    id: str
    timestamp: datetime
    action: str
    snapshot: Dict[str, Any]
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=data["action"],
            snapshot=dict(data.get("snapshot", {})),
            notes=data.get("notes", ""),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "snapshot": self.snapshot,
            "notes": self.notes,
            "metadata": self.metadata,
        }
