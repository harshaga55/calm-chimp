from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List
from uuid import uuid4

from ..core import JsonDatabase, StudyTask
from .registry import register_api

database = JsonDatabase()


def _parse_due_date(due_date: str) -> str:
    try:
        return date.fromisoformat(due_date).isoformat()
    except ValueError as exc:  # noqa: BLE001
        raise ValueError("due_date must be in YYYY-MM-DD format") from exc


@register_api(
    "create_study_task",
    description="Create a new study task with the provided subject, title, and due date.",
    category="tasks",
    tags=("create", "task"),
)
def create_study_task(
    subject: str,
    title: str,
    due_date: str,
    estimated_hours: float,
    notes: str,
) -> Dict[str, object]:
    task = StudyTask(
        id=f"{subject.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        subject=subject,
        title=title,
        due_date=date.fromisoformat(_parse_due_date(due_date)),
        estimated_hours=estimated_hours,
        status="pending",
        notes=notes,
    )
    database.upsert_task(task)
    return {"task": task.to_dict()}


@register_api(
    "mark_task_completed",
    description="Mark a task as completed by its identifier.",
    category="tasks",
    tags=("status", "complete"),
)
def mark_task_completed(task_id: str) -> Dict[str, object]:
    database.update_task_status(task_id, "completed")
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "mark_task_pending",
    description="Reopen a task by setting its status to pending.",
    category="tasks",
    tags=("status", "pending"),
)
def mark_task_pending(task_id: str) -> Dict[str, object]:
    database.update_task_status(task_id, "pending")
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "list_pending_tasks_ordered_by_due_date",
    description="List all pending tasks sorted by due date ascending.",
    category="tasks",
    tags=("list", "pending", "due-date"),
)
def list_pending_tasks_ordered_by_due_date() -> Dict[str, List[dict]]:
    tasks = [
        task.to_dict()
        for task in sorted(
            database.list_tasks(),
            key=lambda t: (t.due_date, t.title),
        )
        if task.status == "pending"
    ]
    return {"tasks": tasks}


@register_api(
    "list_completed_tasks_recent_first",
    description="List completed tasks sorted by most recent history entry.",
    category="tasks",
    tags=("list", "completed"),
)
def list_completed_tasks_recent_first() -> Dict[str, List[dict]]:
    tasks = [
        task.to_dict()
        for task in database.list_tasks()[::-1]
        if task.status == "completed"
    ]
    return {"tasks": tasks}


@register_api(
    "list_tasks_due_today",
    description="List tasks due today.",
    category="tasks",
    tags=("list", "due-today"),
)
def list_tasks_due_today() -> Dict[str, List[dict]]:
    today = date.today()
    tasks = [task.to_dict() for task in database.list_tasks() if task.due_date == today]
    return {"tasks": tasks, "date": today.isoformat()}


@register_api(
    "list_tasks_due_tomorrow",
    description="List tasks due tomorrow.",
    category="tasks",
    tags=("list", "due-tomorrow"),
)
def list_tasks_due_tomorrow() -> Dict[str, List[dict]]:
    target = date.today() + timedelta(days=1)
    tasks = [task.to_dict() for task in database.list_tasks() if task.due_date == target]
    return {"tasks": tasks, "date": target.isoformat()}


@register_api(
    "list_tasks_due_this_week",
    description="List tasks due within the next seven days.",
    category="tasks",
    tags=("list", "due-week"),
)
def list_tasks_due_this_week() -> Dict[str, List[dict]]:
    today = date.today()
    limit = today + timedelta(days=7)
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if today <= task.due_date <= limit
    ]
    return {"tasks": tasks, "start": today.isoformat(), "end": limit.isoformat()}


@register_api(
    "list_overdue_tasks",
    description="List tasks past their due date and still pending.",
    category="tasks",
    tags=("list", "overdue"),
)
def list_overdue_tasks() -> Dict[str, List[dict]]:
    today = date.today()
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if task.due_date < today and task.status != "completed"
    ]
    return {"tasks": tasks, "reference": today.isoformat()}


@register_api(
    "add_note_to_task",
    description="Append a note to a task.",
    category="tasks",
    tags=("notes",),
)
def add_note_to_task(task_id: str, note: str) -> Dict[str, object]:
    database.add_task_note(task_id, note)
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "delete_task_by_id",
    description="Delete a task permanently by its identifier.",
    category="tasks",
    tags=("delete",),
)
def delete_task_by_id(task_id: str) -> Dict[str, object]:
    removed = database.delete_task(task_id)
    return {"deleted": removed, "task_id": task_id}


@register_api(
    "duplicate_task_to_subject",
    description="Duplicate a task into another subject with a new due date.",
    category="tasks",
    tags=("duplicate",),
)
def duplicate_task_to_subject(task_id: str, target_subject: str, new_due_date: str) -> Dict[str, object]:
    original = database.get_task(task_id)
    if not original:
        raise ValueError(f"Task {task_id} not found.")
    task = StudyTask(
        id=f"{target_subject.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        subject=target_subject,
        title=original.title,
        due_date=date.fromisoformat(_parse_due_date(new_due_date)),
        estimated_hours=original.estimated_hours,
        status="pending",
        notes=original.notes,
        plan=list(original.plan),
    )
    database.upsert_task(task)
    return {"task": task.to_dict(), "source_task_id": task_id}


@register_api(
    "update_task_due_date",
    description="Update the due date for a task.",
    category="tasks",
    tags=("update", "due-date"),
)
def update_task_due_date(task_id: str, due_date: str) -> Dict[str, object]:
    database.update_task_due_date(task_id, _parse_due_date(due_date))
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "get_task_details",
    description="Get the details of a task by identifier.",
    category="tasks",
    tags=("get",),
)
def get_task_details(task_id: str) -> Dict[str, object]:
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "reschedule_task_to_today",
    description="Move a task's due date to today.",
    category="calendar",
    tags=("reschedule", "today"),
)
def reschedule_task_to_today(task_id: str) -> Dict[str, object]:
    today_iso = date.today().isoformat()
    database.update_task_due_date(task_id, today_iso)
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "reschedule_task_to_tomorrow",
    description="Move a task's due date to tomorrow.",
    category="calendar",
    tags=("reschedule", "tomorrow"),
)
def reschedule_task_to_tomorrow(task_id: str) -> Dict[str, object]:
    target_iso = (date.today() + timedelta(days=1)).isoformat()
    database.update_task_due_date(task_id, target_iso)
    task = database.get_task(task_id)
    return {"task": task.to_dict() if task else None}


@register_api(
    "reschedule_task_next_week",
    description="Move a task's due date forward by seven days.",
    category="calendar",
    tags=("reschedule", "next-week"),
)
def reschedule_task_next_week(task_id: str) -> Dict[str, object]:
    task = database.get_task(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found.")
    new_due = (task.due_date + timedelta(days=7)).isoformat()
    database.update_task_due_date(task_id, new_due)
    updated = database.get_task(task_id)
    return {"task": updated.to_dict() if updated else None, "previous_due_date": task.due_date.isoformat()}


@register_api(
    "list_tasks_for_subject",
    description="List all tasks for a given subject.",
    category="tasks",
    tags=("list", "subject"),
)
def list_tasks_for_subject(subject: str) -> Dict[str, List[dict]]:
    tasks = [task.to_dict() for task in database.list_tasks() if task.subject == subject]
    return {"tasks": tasks, "subject": subject}


@register_api(
    "list_recently_added_tasks",
    description="List the ten most recently created or updated tasks.",
    category="tasks",
    tags=("list", "recent"),
)
def list_recently_added_tasks() -> Dict[str, List[dict]]:
    tasks = [task.to_dict() for task in database.list_tasks()][-10:]
    return {"tasks": tasks}
