from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, TypedDict

from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph

from ..core.models import StudyTask


class PlannerState(TypedDict, total=False):
    request: Dict[str, object]
    outline: List[str]
    plan: List[str]
    tasks: List[StudyTask]


def _normalize_outline(request: Dict[str, object]) -> List[str]:
    if toc := request.get("table_of_contents"):
        if isinstance(toc, str):
            return [line.strip() for line in toc.splitlines() if line.strip()]
        if isinstance(toc, list):
            return [str(item).strip() for item in toc if str(item).strip()]
    description = str(request.get("description", "Study plan")).strip()
    return [description]


def _chunk_outline(outline: List[str]) -> List[str]:
    chunks: List[str] = []
    for item in outline:
        parts = [part.strip() for part in item.replace(" - ", "|").split("|") if part.strip()]
        if parts:
            chunks.extend(parts)
        else:
            chunks.append(item)
    return chunks


def _build_plan(state: PlannerState) -> PlannerState:
    request = state["request"]
    outline = _chunk_outline(state["outline"])
    estimated_hours = float(request.get("hours_per_section", 2.0))
    due_date_raw = str(request.get("due_date", date.today().isoformat()))
    try:
        due_date = date.fromisoformat(due_date_raw)
    except ValueError:
        due_date = date.today()
    subject = str(request.get("subject", "General Studies"))
    base_id = str(request.get("id", subject.lower().replace(" ", "-")))
    tasks: List[StudyTask] = []
    for idx, title in enumerate(outline, start=1):
        task = StudyTask(
            id=f"{base_id}-{idx}",
            subject=subject,
            title=title,
            due_date=due_date,
            estimated_hours=estimated_hours,
            status="pending",
            plan=[f"Review {title}", f"Summarize {title}", f"Practice {title}"],
        )
        tasks.append(task)
    state["plan"] = [step for task in tasks for step in task.plan]
    state["tasks"] = tasks
    return state


def _ingest_node(state: PlannerState) -> PlannerState:
    request = state.get("request", {})
    outline = _normalize_outline(request)
    state["outline"] = outline
    return state


graph = StateGraph(PlannerState)
graph.add_node("ingest", RunnableLambda(_ingest_node))
graph.add_node("build_plan", RunnableLambda(_build_plan))
graph.set_entry_point("ingest")
graph.add_edge("ingest", "build_plan")
graph.add_edge("build_plan", END)
planner_graph = graph.compile()


@dataclass
class PlannerAgent:
    graph = planner_graph

    def plan(self, request: Dict[str, object]) -> List[StudyTask]:
        result: PlannerState = self.graph.invoke({"request": request})
        return result["tasks"]
