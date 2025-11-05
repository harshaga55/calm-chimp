from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QSplitter

from ..api import api_state
from ..config.settings import AppSettings
from ..domain import CalendarEvent, Category
from ..orchestrator import LangGraphOrchestrator
from ..utils.qt import TaskRunner
from .components.calendar_panel import CalendarPanel
from .components.category_dialog import CategoryDialog
from .components.chat_panel import ChatPanel
from .components.event_dialog import EventDialog
from .components.sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(self, *, api_state=api_state, settings: AppSettings) -> None:
        super().__init__()
        self.api_state = api_state
        self.settings = settings
        self.runner = TaskRunner()
        self.orchestrator = LangGraphOrchestrator()

        self.setWindowTitle(f"{settings.ui.app_name} — Supabase Calendar")
        self.resize(1400, 820)

        self.sidebar = Sidebar()
        self.calendar_panel = CalendarPanel()
        self.chat_panel = ChatPanel(orchestrator=self.orchestrator, runner=self.runner)

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self.calendar_panel)
        splitter.addWidget(self.chat_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)

        self.setCentralWidget(splitter)

        self.sidebar.refresh_requested.connect(self.refresh_timeline)
        self.sidebar.create_category_requested.connect(self.create_category)
        self.sidebar.new_event_requested.connect(self.create_event)
        self.sidebar.category_selected.connect(self.filter_by_category)

        self.calendar_panel.day_changed.connect(self.load_day)
        self.chat_panel.tool_executed.connect(self._handle_tool_execution)

        self._categories: List[Category] = []
        self._selected_day: date = date.today()
        self._initialize_ui()

    # ------------------------------------------------------------------ boot

    def _initialize_ui(self) -> None:
        self.statusBar().showMessage("Loading Supabase data...")
        self.load_profile()
        self.refresh_timeline()

    # ------------------------------------------------------------------ data fetchers

    def load_profile(self) -> None:
        def worker():
            user_id = self.api_state.context.gateway.current_user_id()
            profile = self.api_state.context.profiles.fetch(user_id)
            if profile:
                return profile
            session = self.api_state.context.gateway.session()
            email = getattr(getattr(session, "user", None), "email", "")
            return {"email": email, "full_name": None}

        def done(result):
            email = getattr(result, "email", result.get("email"))
            full_name = getattr(result, "full_name", result.get("full_name"))
            self.sidebar.set_user(email=email, full_name=full_name)

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def refresh_timeline(self) -> None:
        self.statusBar().showMessage("Refreshing timeline cache…")

        def worker():
            self.api_state.calendar.prime_cache()
            return self.api_state.calendar.cache

        def done(_cache):
            self.statusBar().showMessage("Timeline synchronized.", 4000)
            self.load_categories()
            self.load_day(self._selected_day.isoformat())

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def load_categories(self) -> None:
        def worker():
            return self.api_state.categories.list_categories()

        def done(categories: List[Category]):
            self._categories = categories
            self.sidebar.set_categories(categories)

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def load_day(self, day_iso: str) -> None:
        try:
            target_date = date.fromisoformat(day_iso)
        except ValueError:
            target_date = date.today()
        self._selected_day = target_date

        def worker() -> List[CalendarEvent]:
            return self.api_state.calendar.list_for_day(target_date)

        def done(events: List[CalendarEvent]) -> None:
            self.calendar_panel.set_day(target_date)
            self.calendar_panel.populate_events(events)

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    # ------------------------------------------------------------------ actions

    def filter_by_category(self, category: Optional[Category]) -> None:
        if not category:
            self.load_day(self._selected_day.isoformat())
            return

        def worker() -> List[CalendarEvent]:
            events = self.api_state.calendar.list_for_day(self._selected_day)
            return [event for event in events if event.category_id == category.id]

        def done(events: List[CalendarEvent]) -> None:
            self.calendar_panel.populate_events(events)

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def create_category(self) -> None:
        dialog = CategoryDialog()
        if dialog.exec() != CategoryDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values["name"]:
            QMessageBox.warning(self, "Invalid", "Category name is required.")
            return

        def worker() -> Category:
            return self.api_state.categories.upsert_category(**values)

        def done(_category: Category) -> None:
            self.load_categories()
            self.statusBar().showMessage("Category saved.", 3000)

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def create_event(self) -> None:
        start = datetime.combine(self._selected_day, datetime.now().time()).replace(hour=9, minute=0, second=0)
        end = start + timedelta(hours=1)
        dialog = EventDialog(categories=self._categories, default_start=start, default_end=end)
        if dialog.exec() != EventDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        title = values.pop("title")
        if not title:
            QMessageBox.warning(self, "Missing title", "Provide a title for the event.")
            return

        def worker() -> CalendarEvent:
            return self.api_state.calendar.upsert_event(title=title, **values)

        def done(_event: CalendarEvent) -> None:
            self.statusBar().showMessage("Event saved.", 3000)
            self.refresh_timeline()

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    # ------------------------------------------------------------------ chat integration

    def _handle_tool_execution(self, tool_name: str, arguments: dict, output: dict) -> None:
        if tool_name in {"refresh_timeline", "upsert_event", "delete_event"}:
            self.refresh_timeline()
        elif tool_name == "events_for_day":
            day = arguments.get("day") or output.get("day")
            if day:
                self.load_day(day)
        elif tool_name == "list_categories":
            self.load_categories()

    # ------------------------------------------------------------------ misc

    def _handle_error(self, exc: Exception) -> None:
        self.statusBar().showMessage(f"Error: {exc}", 5000)
        QMessageBox.critical(self, "Error", str(exc))
