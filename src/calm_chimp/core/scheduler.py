from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from .models import StudyTask


def distribute_plan(task: StudyTask) -> Dict[date, List[str]]:
    """Spread the task plan evenly across days until due date."""
    today = date.today()
    remaining_days = max((task.due_date - today).days + 1, 1)
    plan_items = list(task.plan) or [task.title]
    daily_plan: Dict[date, List[str]] = {}
    for index, item in enumerate(plan_items):
        task_day = today + timedelta(days=index % remaining_days)
        daily_plan.setdefault(task_day, []).append(item)
    return daily_plan
