from __future__ import annotations

from typing import Dict, List

from ..core import JsonDatabase, StudySubject
from .registry import register_api

database = JsonDatabase()


@register_api(
    "create_subject",
    description="Create a new study subject with a description.",
    category="subjects",
    tags=("create",),
)
def create_subject(name: str, description: str) -> Dict[str, object]:
    subject = StudySubject(name=name, description=description)
    database.upsert_subject(subject)
    return {"subject": subject.to_dict()}


@register_api(
    "update_subject_description",
    description="Replace the description for a subject.",
    category="subjects",
    tags=("update", "description"),
)
def update_subject_description(name: str, description: str) -> Dict[str, object]:
    database.update_subject_description(name, description)
    subject = database.get_subject(name)
    return {"subject": subject.to_dict() if subject else None}


@register_api(
    "assign_subject_color",
    description="Assign a color hex code to a subject.",
    category="subjects",
    tags=("update", "color"),
)
def assign_subject_color(name: str, color_hex: str) -> Dict[str, object]:
    database.update_subject_color(name, color_hex)
    subject = database.get_subject(name)
    return {"subject": subject.to_dict() if subject else None}


@register_api(
    "list_all_subjects",
    description="List all subjects alphabetically.",
    category="subjects",
    tags=("list",),
)
def list_all_subjects() -> Dict[str, List[dict]]:
    subjects = sorted(database.list_subjects(), key=lambda s: s.name.lower())
    return {"subjects": [subject.to_dict() for subject in subjects]}


@register_api(
    "list_subjects_with_task_counts",
    description="List all subjects with counts of tasks under each subject.",
    category="subjects",
    tags=("list", "counts"),
)
def list_subjects_with_task_counts() -> Dict[str, List[dict]]:
    subjects = {subject.name: subject.to_dict() for subject in database.list_subjects()}
    counts = {}
    for task in database.list_tasks():
        counts[task.subject] = counts.get(task.subject, 0) + 1
    payload = []
    for name, subject in subjects.items():
        payload.append({**subject, "task_count": counts.get(name, 0)})
    return {"subjects": sorted(payload, key=lambda item: item["name"].lower())}


@register_api(
    "delete_subject_and_tasks",
    description="Delete a subject and all tasks associated with it.",
    category="subjects",
    tags=("delete",),
)
def delete_subject_and_tasks(name: str) -> Dict[str, object]:
    removed = database.delete_subject(name, remove_tasks=True)
    return {"deleted": removed, "subject": name}
