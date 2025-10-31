from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from ..core import JsonDatabase, distribute_plan
from .registry import register_api

database = JsonDatabase()


def _parse_day(day: str) -> date:
    try:
        return date.fromisoformat(day)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError("day must be formatted YYYY-MM-DD") from exc


@register_api(
    "calendar_tasks_for_day",
    description="Return tasks scheduled or due on a specific day.",
    category="calendar",
    tags=("calendar", "day"),
)
def calendar_tasks_for_day(day: str) -> Dict[str, List[dict]]:
    target = _parse_day(day)
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if task.due_date == target
    ]
    return {"date": target.isoformat(), "tasks": tasks}


@register_api(
    "calendar_tasks_for_week",
    description="Return tasks due within a seven day window starting from the provided day.",
    category="calendar",
    tags=("calendar", "week"),
)
def calendar_tasks_for_week(start_day: str) -> Dict[str, List[dict]]:
    start = _parse_day(start_day)
    end = start + timedelta(days=6)
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if start <= task.due_date <= end
    ]
    return {"start": start.isoformat(), "end": end.isoformat(), "tasks": tasks}


@register_api(
    "calendar_tasks_for_subject",
    description="Return tasks for a specific subject and day.",
    category="calendar",
    tags=("calendar", "subject"),
)
def calendar_tasks_for_subject(subject: str, day: str) -> Dict[str, List[dict]]:
    target = _parse_day(day)
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if task.subject == subject and task.due_date == target
    ]
    return {"subject": subject, "date": target.isoformat(), "tasks": tasks}


@register_api(
    "calendar_generate_daily_schedule_for_task",
    description="Generate the per-day schedule entries for a single task.",
    category="calendar",
    tags=("calendar", "schedule"),
)
def calendar_generate_daily_schedule_for_task(task_id: str) -> Dict[str, List[str]]:
    task = database.get_task(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found.")
    schedule = {day.isoformat(): plan for day, plan in distribute_plan(task).items()}
    return {"task_id": task_id, "schedule": schedule}


@register_api(
    "calendar_tasks_due_in_days",
    description="Return tasks due in an exact number of days from today.",
    category="calendar",
    tags=("calendar", "relative"),
)
def calendar_tasks_due_in_days(days_ahead: int) -> Dict[str, List[dict]]:
    reference = date.today() + timedelta(days=days_ahead)
    tasks = [
        task.to_dict()
        for task in database.list_tasks()
        if task.due_date == reference
    ]
    return {"date": reference.isoformat(), "tasks": tasks, "offset_days": days_ahead}
