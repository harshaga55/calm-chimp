from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List

from ..agents import PlannerAgent
from ..core import JsonDatabase
from .registry import register_api

database = JsonDatabase()
planner = PlannerAgent()


def _normalize_outline_lines(lines: List[str]) -> List[str]:
    return [line.strip() for line in lines if line.strip()]


@register_api(
    "generate_plan_from_outline",
    description="Generate study tasks from an explicit outline list.",
    category="planning",
    tags=("planning", "outline"),
)
def generate_plan_from_outline(
    subject: str,
    due_date: str,
    outline_lines: List[str],
    hours_per_section: float,
) -> Dict[str, List[dict]]:
    request = {
        "id": f"{subject.lower().replace(' ', '-')}",
        "subject": subject,
        "due_date": due_date,
        "table_of_contents": _normalize_outline_lines(outline_lines),
        "hours_per_section": hours_per_section,
        "description": f"Plan for {subject}",
    }
    tasks = planner.plan(request)
    for task in tasks:
        database.upsert_task(task)
    return {"tasks": [task.to_dict() for task in tasks]}


@register_api(
    "generate_plan_from_description",
    description="Generate a plan from a single description string.",
    category="planning",
    tags=("planning", "description"),
)
def generate_plan_from_description(
    subject: str,
    due_date: str,
    description: str,
    hours_per_section: float,
) -> Dict[str, List[dict]]:
    request = {
        "id": f"{subject.lower().replace(' ', '-')}",
        "subject": subject,
        "due_date": due_date,
        "description": description,
        "hours_per_section": hours_per_section,
    }
    tasks = planner.plan(request)
    for task in tasks:
        database.upsert_task(task)
    return {"tasks": [task.to_dict() for task in tasks]}


@register_api(
    "generate_plan_from_outline_file",
    description="Generate tasks from a text file containing outline lines.",
    category="planning",
    tags=("planning", "file"),
)
def generate_plan_from_outline_file(
    subject: str,
    due_date: str,
    outline_file_path: str,
    hours_per_section: float,
) -> Dict[str, List[dict]]:
    path = Path(outline_file_path).expanduser().resolve()
    contents = path.read_text(encoding="utf-8").splitlines()
    return generate_plan_from_outline(subject, due_date, contents, hours_per_section)


@register_api(
    "generate_review_plan_for_existing_tasks",
    description="Create a review plan for tasks already stored under a subject without altering existing tasks.",
    category="planning",
    tags=("planning", "review"),
)
def generate_review_plan_for_existing_tasks(subject: str, due_date: str, hours_per_section: float) -> Dict[str, List[dict]]:
    outline = [task.title for task in database.list_tasks() if task.subject == subject]
    request = {
        "id": f"{subject.lower().replace(' ', '-')}-review",
        "subject": subject,
        "due_date": due_date,
        "table_of_contents": _normalize_outline_lines(outline),
        "hours_per_section": hours_per_section,
        "description": f"Review plan for {subject}",
    }
    tasks = planner.plan(request)
    return {"tasks": [task.to_dict() for task in tasks]}
