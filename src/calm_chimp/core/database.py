from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import orjson

from .config import DATABASE_FILE, DEFAULT_DATABASE_CONTENT, ensure_data_dir
from .models import HistoryEntry, StudySubject, StudyTask


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
