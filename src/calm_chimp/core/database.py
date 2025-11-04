from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import orjson

from .config import DATABASE_FILE, DEFAULT_DATABASE_CONTENT, ensure_data_dir
from .models import HistoryEntry, StudySubject, StudyTask
from .supabase_client import (
    SupabaseNotConfiguredError,
    SupabaseSessionMissingError,
    current_user_id,
    get_supabase_client,
)


class JsonDatabase:
    def __init__(self, path: Optional[Path] = None) -> None:
        ensure_data_dir()
        self._path = path or DATABASE_FILE
        self._cache: Dict[str, List[dict] | dict] | None = None

    def _load_raw(self) -> Dict[str, List[dict] | dict]:
        if self._cache is None:
            if not self._path.exists():
                ensure_data_dir()
                self._path.write_text(json.dumps(DEFAULT_DATABASE_CONTENT) + "\n", encoding="utf-8")
            data = orjson.loads(self._path.read_bytes() or b"{}")
            self._cache = {
                "tasks": list(data.get("tasks", [])),
                "subjects": list(data.get("subjects", [])),
                "history": list(data.get("history", [])),
                "metadata": dict(data.get("metadata", {})),
            }
        return self._cache

    def _persist(self) -> None:
        if self._cache is None:
            return
        payload = orjson.dumps(self._cache, option=orjson.OPT_INDENT_2)
        self._path.write_bytes(payload + b"\n")

    def list_tasks(self) -> List[StudyTask]:
        return [StudyTask.from_dict(item) for item in self._load_raw()["tasks"]]

    def list_subjects(self) -> List[StudySubject]:
        return [StudySubject.from_dict(item) for item in self._load_raw()["subjects"]]

    def list_history(self) -> List[HistoryEntry]:
        return [HistoryEntry.from_dict(item) for item in self._load_raw()["history"]]

    def _snapshot(self) -> Dict[str, list]:
        data = self._load_raw()
        return {
            "tasks": deepcopy(data["tasks"]),
            "subjects": deepcopy(data["subjects"]),
        }

    def _append_history(self, action: str, notes: str = "", metadata: Optional[dict] = None) -> None:
        data = self._load_raw()
        history = data["history"]
        entry = HistoryEntry(
            id=datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
            timestamp=datetime.utcnow(),
            action=action,
            snapshot=self._snapshot(),
            notes=notes,
            metadata=metadata or {},
        )
        history.append(entry.to_dict())

    def upsert_task(self, task: StudyTask) -> None:
        data = self._load_raw()
        items = data["tasks"]
        for idx, existing in enumerate(items):
            if existing["id"] == task.id:
                items[idx] = task.to_dict()
                break
        else:
            items.append(task.to_dict())
        self._append_history(action="upsert_task", metadata={"task_id": task.id})
        self._persist()

    def upsert_subject(self, subject: StudySubject) -> None:
        data = self._load_raw()
        items = data["subjects"]
        for idx, existing in enumerate(items):
            if existing["name"] == subject.name:
                items[idx] = subject.to_dict()
                break
        else:
            items.append(subject.to_dict())
        self._append_history(action="upsert_subject", metadata={"subject": subject.name})
        self._persist()

    def update_task_status(self, task_id: str, status: str) -> None:
        data = self._load_raw()
        for item in data["tasks"]:
            if item["id"] == task_id:
                item["status"] = status
                break
        self._append_history(action="update_task_status", metadata={"task_id": task_id, "status": status})
        self._persist()

    def get_task(self, task_id: str) -> Optional[StudyTask]:
        for task in self.list_tasks():
            if task.id == task_id:
                return task
        return None

    def get_subject(self, name: str) -> Optional[StudySubject]:
        for subject in self.list_subjects():
            if subject.name == name:
                return subject
        return None

    def update_task_due_date(self, task_id: str, due_date: str) -> None:
        data = self._load_raw()
        for item in data["tasks"]:
            if item["id"] == task_id:
                item["due_date"] = due_date
                break
        self._append_history(action="update_task_due_date", metadata={"task_id": task_id, "due_date": due_date})
        self._persist()

    def add_task_note(self, task_id: str, note: str) -> None:
        data = self._load_raw()
        for item in data["tasks"]:
            if item["id"] == task_id:
                existing = item.get("notes", "")
                item["notes"] = f"{existing}\n{note}".strip()
                break
        self._append_history(action="add_task_note", metadata={"task_id": task_id})
        self._persist()

    def delete_task(self, task_id: str) -> bool:
        data = self._load_raw()
        items = data["tasks"]
        for idx, item in enumerate(items):
            if item["id"] == task_id:
                del items[idx]
                self._append_history(action="delete_task", metadata={"task_id": task_id})
                self._persist()
                return True
        return False

    def delete_subject(self, subject_name: str, *, remove_tasks: bool = False) -> bool:
        data = self._load_raw()
        subjects = data["subjects"]
        for idx, item in enumerate(subjects):
            if item["name"] == subject_name:
                del subjects[idx]
                break
        else:
            return False
        if remove_tasks:
            data["tasks"] = [task for task in data["tasks"] if task["subject"] != subject_name]
        self._append_history(
            action="delete_subject",
            metadata={"subject": subject_name, "remove_tasks": remove_tasks},
        )
        self._persist()
        return True

    def update_subject_description(self, subject_name: str, description: str) -> None:
        data = self._load_raw()
        for item in data["subjects"]:
            if item["name"] == subject_name:
                item["description"] = description
                break
        else:
            data["subjects"].append({"name": subject_name, "description": description, "color": None})
        self._append_history(action="update_subject_description", metadata={"subject": subject_name})
        self._persist()

    def update_subject_color(self, subject_name: str, color: str) -> None:
        data = self._load_raw()
        for item in data["subjects"]:
            if item["name"] == subject_name:
                item["color"] = color
                break
        else:
            data["subjects"].append({"name": subject_name, "description": "", "color": color})
        self._append_history(action="update_subject_color", metadata={"subject": subject_name, "color": color})
        self._persist()

    def overwrite_state(self, snapshot: Dict[str, list]) -> None:
        data = self._load_raw()
        data["tasks"] = deepcopy(snapshot.get("tasks", []))
        data["subjects"] = deepcopy(snapshot.get("subjects", []))
        self._append_history(action="overwrite_state", metadata={"source": "history_revert"})
        self._persist()

    def revert_to_history(self, history_id: str) -> Optional[HistoryEntry]:
        entries = self.list_history()
        for entry in reversed(entries):
            if entry.id == history_id:
                self.overwrite_state(entry.snapshot)
                return entry
        return None
        self._persist()


TASKS_TABLE = "user_events"
SUBJECTS_TABLE = "user_subjects"
HISTORY_TABLE = "history_entries"


class SupabaseDatabase:
    """Supabase-backed persistence layer sharing the JsonDatabase interface."""

    def __init__(self) -> None:
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = get_supabase_client()
            except SupabaseNotConfiguredError as exc:  # noqa: TRY003
                raise SupabaseNotConfiguredError("Supabase client is not initialized. Call initialize_supabase().") from exc
        return self._client

    def list_tasks(self) -> List[StudyTask]:
        user_id = current_user_id()
        response = self.client.table(TASKS_TABLE).select("*").eq("user_id", user_id).order("due_date").execute()
        records = response.data or []
        tasks: List[StudyTask] = []
        for row in records:
            tasks.append(StudyTask.from_dict(self._deserialize_task(row)))
        return tasks

    def list_subjects(self) -> List[StudySubject]:
        user_id = current_user_id()
        response = self.client.table(SUBJECTS_TABLE).select("*").eq("user_id", user_id).order("name").execute()
        subjects: List[StudySubject] = []
        for row in response.data or []:
            subjects.append(StudySubject.from_dict(self._deserialize_subject(row)))
        return subjects

    def list_history(self) -> List[HistoryEntry]:
        user_id = current_user_id()
        response = (
            self.client.table(HISTORY_TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=False)
            .execute()
        )
        entries: List[HistoryEntry] = []
        for row in response.data or []:
            entries.append(HistoryEntry.from_dict(self._deserialize_history(row)))
        return entries

    def upsert_task(self, task: StudyTask) -> None:
        user_id = current_user_id()
        payload = self._serialize_task(task, user_id)
        self.client.table(TASKS_TABLE).upsert(payload).execute()
        self._append_history(action="upsert_task", metadata={"task_id": task.id})

    def upsert_subject(self, subject: StudySubject) -> None:
        user_id = current_user_id()
        record = self._serialize_subject(subject, user_id)
        self.client.table(SUBJECTS_TABLE).upsert(record).execute()
        self._append_history(action="upsert_subject", metadata={"subject": subject.name})

    def update_task_status(self, task_id: str, status: str) -> None:
        user_id = current_user_id()
        self.client.table(TASKS_TABLE).update({"status": status}).eq("id", task_id).eq("user_id", user_id).execute()
        self._append_history(action="update_task_status", metadata={"task_id": task_id, "status": status})

    def get_task(self, task_id: str) -> Optional[StudyTask]:
        user_id = current_user_id()
        response = self.client.table(TASKS_TABLE).select("*").eq("id", task_id).eq("user_id", user_id).limit(1).execute()
        if not response.data:
            return None
        return StudyTask.from_dict(self._deserialize_task(response.data[0]))

    def get_subject(self, name: str) -> Optional[StudySubject]:
        user_id = current_user_id()
        response = self.client.table(SUBJECTS_TABLE).select("*").eq("name", name).eq("user_id", user_id).limit(1).execute()
        if not response.data:
            return None
        return StudySubject.from_dict(self._deserialize_subject(response.data[0]))

    def update_task_due_date(self, task_id: str, due_date: str) -> None:
        user_id = current_user_id()
        self.client.table(TASKS_TABLE).update({"due_date": due_date}).eq("id", task_id).eq("user_id", user_id).execute()
        self._append_history(action="update_task_due_date", metadata={"task_id": task_id, "due_date": due_date})

    def add_task_note(self, task_id: str, note: str) -> None:
        task = self.get_task(task_id)
        if task is None:
            return
        existing = task.notes or ""
        updated_notes = f"{existing}\n{note}".strip()
        user_id = current_user_id()
        self.client.table(TASKS_TABLE).update({"notes": updated_notes}).eq("id", task_id).eq("user_id", user_id).execute()
        self._append_history(action="add_task_note", metadata={"task_id": task_id})

    def delete_task(self, task_id: str) -> bool:
        user_id = current_user_id()
        response = self.client.table(TASKS_TABLE).delete().eq("id", task_id).eq("user_id", user_id).execute()
        deleted = bool(response.data)
        if deleted:
            self._append_history(action="delete_task", metadata={"task_id": task_id})
        return deleted

    def delete_subject(self, subject_name: str, *, remove_tasks: bool = False) -> bool:
        user_id = current_user_id()
        response = (
            self.client.table(SUBJECTS_TABLE)
            .delete()
            .eq("name", subject_name)
            .eq("user_id", user_id)
            .execute()
        )
        deleted = bool(response.data)
        if not deleted:
            return False
        if remove_tasks:
            self.client.table(TASKS_TABLE).delete().eq("subject", subject_name).eq("user_id", user_id).execute()
        self._append_history(
            action="delete_subject",
            metadata={"subject": subject_name, "remove_tasks": remove_tasks},
        )
        return True

    def update_subject_description(self, subject_name: str, description: str) -> None:
        subject = self.get_subject(subject_name)
        if subject is None:
            subject = StudySubject(name=subject_name, description=description)
        else:
            subject.description = description
        self.upsert_subject(subject)

    def update_subject_color(self, subject_name: str, color: str) -> None:
        subject = self.get_subject(subject_name)
        if subject is None:
            subject = StudySubject(name=subject_name, color=color)
        else:
            subject.color = color
        self.upsert_subject(subject)

    def overwrite_state(self, snapshot: Dict[str, list]) -> None:
        user_id = current_user_id()
        self.client.table(TASKS_TABLE).delete().eq("user_id", user_id).execute()
        self.client.table(SUBJECTS_TABLE).delete().eq("user_id", user_id).execute()

        tasks_payload = [
            self._serialize_task(StudyTask.from_dict(task_dict), user_id)
            for task_dict in snapshot.get("tasks", [])
        ]
        subjects_payload = [
            self._serialize_subject(StudySubject.from_dict(subject_dict), user_id)
            for subject_dict in snapshot.get("subjects", [])
        ]
        if tasks_payload:
            self.client.table(TASKS_TABLE).upsert(tasks_payload).execute()
        if subjects_payload:
            self.client.table(SUBJECTS_TABLE).upsert(subjects_payload).execute()
        self._append_history(action="overwrite_state", metadata={"source": "history_revert"})

    def revert_to_history(self, history_id: str) -> Optional[HistoryEntry]:
        user_id = current_user_id()
        response = (
            self.client.table(HISTORY_TABLE)
            .select("*")
            .eq("id", history_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        entry = HistoryEntry.from_dict(self._deserialize_history(response.data[0]))
        self.overwrite_state(entry.snapshot)
        return entry

    # Helpers -----------------------------------------------------------------

    def _serialize_task(self, task: StudyTask, user_id: str) -> Dict[str, Any]:
        return {
            "id": task.id,
            "user_id": user_id,
            "subject": task.subject,
            "title": task.title,
            "due_date": task.due_date.isoformat(),
            "estimated_hours": float(task.estimated_hours),
            "status": task.status,
            "notes": task.notes,
            "plan": list(task.plan),
        }

    def _deserialize_task(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "subject": row.get("subject", ""),
            "title": row.get("title", ""),
            "due_date": row.get("due_date"),
            "estimated_hours": row.get("estimated_hours", 1.0),
            "status": row.get("status", "pending"),
            "notes": row.get("notes", ""),
            "plan": row.get("plan") or [],
        }

    def _serialize_subject(self, subject: StudySubject, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "name": subject.name,
            "description": subject.description,
            "color": subject.color,
        }

    def _deserialize_subject(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": row.get("name"),
            "description": row.get("description", ""),
            "color": row.get("color"),
        }

    def _serialize_history(self, entry: HistoryEntry, user_id: str) -> Dict[str, Any]:
        return {
            "id": entry.id,
            "user_id": user_id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action,
            "snapshot": entry.snapshot,
            "notes": entry.notes,
            "metadata": entry.metadata,
        }

    def _deserialize_history(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "timestamp": row.get("timestamp"),
            "action": row.get("action", ""),
            "snapshot": row.get("snapshot") or {},
            "notes": row.get("notes", ""),
            "metadata": row.get("metadata") or {},
        }

    def _snapshot(self) -> Dict[str, list]:
        return {
            "tasks": [task.to_dict() for task in self.list_tasks()],
            "subjects": [subject.to_dict() for subject in self.list_subjects()],
        }

    def _append_history(self, action: str, notes: str = "", metadata: Optional[dict] = None) -> None:
        try:
            user_id = current_user_id()
        except SupabaseSessionMissingError:
            return
        entry = HistoryEntry(
            id=datetime.utcnow().strftime("%Y%m%d%H%M%S%f"),
            timestamp=datetime.utcnow(),
            action=action,
            snapshot=self._snapshot(),
            notes=notes,
            metadata=metadata or {},
        )
        payload = self._serialize_history(entry, user_id)
        self.client.table(HISTORY_TABLE).upsert(payload).execute()
