from __future__ import annotations

import sys
import json
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QCalendarWidget,
    QFrame,
    QMessageBox,
)

from ..api import call_api
from ..core import (
    APP_NAME,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    ensure_data_dir,
    get_supabase_session,
    supabase_ready,
)
from ..llm import ChatOrchestrator
from ..logging import configure_logging
from .auth_dialog import LoginDialog


configure_logging()


class CalendarTab(QWidget):
    def __init__(self, refresher: Callable[[Optional[str]], None]) -> None:
        super().__init__()
        self.refresher = refresher
        layout = QVBoxLayout()
        self.calendar = QCalendarWidget()
        self.calendar.selectionChanged.connect(self.refresh_day)
        layout.addWidget(self.calendar)

        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self.toggle_task)
        layout.addWidget(self.task_list)

        self.setLayout(layout)
        self.refresh_day()

    def _selected_date(self) -> str:
        return self.calendar.selectedDate().toString("yyyy-MM-dd")

    def refresh_day(self, day: Optional[str] = None) -> None:
        if day:
            qdate = QDate.fromString(day, "yyyy-MM-dd")
            if qdate.isValid():
                self.calendar.setSelectedDate(qdate)
        target_day = self._selected_date()
        result = call_api("calendar_tasks_for_day", day=target_day)
        self.task_list.clear()
        for task in result["tasks"]:
            display = f"[{task['status'].upper()}] {task['subject']} — {task['title']} (Due {task['due_date']})"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, task)
            self.task_list.addItem(item)

    def toggle_task(self, item: QListWidgetItem) -> None:
        task = item.data(Qt.ItemDataRole.UserRole)
        if task["status"] == "completed":
            call_api("mark_task_pending", task_id=task["id"])
        else:
            call_api("mark_task_completed", task_id=task["id"])
        self.refresh_day()
        self.refresher()


class ActivityTab(QWidget):
    def __init__(self, refresher: Callable[[Optional[str]], None]) -> None:
        super().__init__()
        self.refresher = refresher
        layout = QVBoxLayout()
        self.history_list = QListWidget()
        layout.addWidget(self.history_list)

        revert_button = QPushButton("Revert to Selected Snapshot")
        revert_button.clicked.connect(self.revert_selected)
        layout.addWidget(revert_button)

        self.setLayout(layout)
        self.refresh_history()

    def refresh_history(self) -> None:
        result = call_api("list_recent_history_actions")
        self.history_list.clear()
        for entry in reversed(result["entries"]):
            label = f"{entry['timestamp']} — {entry['action']} ({entry['id']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)

    def revert_selected(self) -> None:
        current = self.history_list.currentItem()
        if not current:
            QMessageBox.information(self, "No selection", "Choose a history entry to revert.")
            return
        entry = current.data(Qt.ItemDataRole.UserRole)
        call_api("revert_calendar_to_history_entry", history_id=entry["id"])
        self.refresh_history()
        self.refresher()
        QMessageBox.information(self, "Reverted", f"Reverted to snapshot {entry['id']}.")


class PlannerTab(QWidget):
    def __init__(self, refresher: Callable[[Optional[str]], None]) -> None:
        super().__init__()
        self.refresher = refresher
        layout = QVBoxLayout()

        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Subject (e.g., Physics)")

        self.due_input = QLineEdit()
        self.due_input.setPlaceholderText(date.today().isoformat())

        self.hours_input = QLineEdit()
        self.hours_input.setPlaceholderText("2.0")

        self.outline_editor = QTextEdit()
        self.outline_editor.setPlaceholderText("Chapter 1: ...\nChapter 2: ...")

        layout.addWidget(QLabel("Subject"))
        layout.addWidget(self.subject_input)
        layout.addWidget(QLabel("Due Date (YYYY-MM-DD)"))
        layout.addWidget(self.due_input)
        layout.addWidget(QLabel("Hours per Section"))
        layout.addWidget(self.hours_input)
        layout.addWidget(QLabel("Outline Lines"))
        layout.addWidget(self.outline_editor)

        button_row = QHBoxLayout()

        build_plan = QPushButton("Generate Plan from Outline")
        build_plan.clicked.connect(self.generate_plan)
        button_row.addWidget(build_plan)

        load_outline = QPushButton("Load Outline File")
        load_outline.clicked.connect(self.load_outline)
        button_row.addWidget(load_outline)

        layout.addLayout(button_row)

        self.setLayout(layout)

    def _hours(self) -> float:
        try:
            return float(self.hours_input.text() or "2.0")
        except ValueError as exc:  # noqa: BLE001
            raise ValueError("Hours per section must be a number.") from exc

    def generate_plan(self) -> None:
        subject = self.subject_input.text().strip()
        due_date = self.due_input.text().strip() or date.today().isoformat()
        outline = [line.strip() for line in self.outline_editor.toPlainText().splitlines() if line.strip()]

        if not subject:
            QMessageBox.warning(self, "Missing subject", "Please provide a subject.")
            return
        try:
            date.fromisoformat(due_date)
        except ValueError:
            QMessageBox.warning(self, "Invalid date", "Due date must be YYYY-MM-DD.")
            return
        if not outline:
            QMessageBox.warning(self, "Missing outline", "Provide at least one outline line.")
            return

        hours = self._hours()

        result = call_api(
            "generate_plan_from_outline",
            subject=subject,
            due_date=due_date,
            outline_lines=outline,
            hours_per_section=hours,
        )
        QMessageBox.information(
            self,
            "Plan Generated",
            f"Created {len(result['tasks'])} tasks for {subject}.",
        )
        self.refresher()

    def load_outline(self) -> None:
        dialog = QFileDialog(self, "Select outline text file")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("Text Files (*.txt);;All Files (*)")
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        path = Path(dialog.selectedFiles()[0])
        try:
            contents = path.read_text(encoding="utf-8")
            self.outline_editor.setPlainText(contents)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Failed to load file: {exc}")


class ChatMessageWidget(QFrame):
    def __init__(
        self,
        role: str,
        text: str,
        detail_title: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(bubble)

        if role == "user":
            palette = "#e3f2fd"
            text_color = "#0d47a1"
        else:
            palette = "#f1f8e9"
            text_color = "#1b5e20"

        self.setStyleSheet(
            f"QFrame {{ background-color: {palette}; border-radius: 12px; }}"
            f"QLabel {{ color: {text_color}; font-size: 14px; }}"
        )

        self.details_widget: Optional[QPlainTextEdit] = None
        self.toggle_button: Optional[QToolButton] = None

        if details:
            self.toggle_button = QToolButton()
            self.toggle_button.setCheckable(True)
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.toggle_button.setText(detail_title or "Details")
            self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(self.toggle_button, alignment=Qt.AlignmentFlag.AlignRight)

            self.details_widget = QPlainTextEdit()
            self.details_widget.setReadOnly(True)
            self.details_widget.setPlainText(details)
            self.details_widget.setMaximumHeight(180)
            self.details_widget.hide()
            layout.addWidget(self.details_widget)

            self.toggle_button.toggled.connect(self._toggle_details)

    def _toggle_details(self, checked: bool) -> None:
        if not self.details_widget or not self.toggle_button:
            return
        self.details_widget.setVisible(checked)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)


class ChatPanel(QWidget):
    HELP_TEXT = (
        "Commands:\n"
        "/plan subject=<name>;due=<YYYY-MM-DD>;hours=<float>;outline=line1|line2\n"
        "/pending – list pending tasks\n"
        "/overdue – list overdue tasks\n"
        "/today – list tasks due today\n"
        "/history – show recent history\n"
        "/tools – list available MCP tools\n"
        "Natural questions are routed through your Azure OpenAI deployment when configured."
    )

    def __init__(self, refresher: Callable[[Optional[str]], None]) -> None:
        super().__init__()
        self.refresher = refresher
        self.orchestrator = ChatOrchestrator()
        self.history: List[Dict[str, str]] = []

        layout = QVBoxLayout()

        self.conversation_area = QScrollArea()
        self.conversation_area.setWidgetResizable(True)
        self.conversation_container = QWidget()
        self.conversation_layout = QVBoxLayout(self.conversation_container)
        self.conversation_layout.setContentsMargins(12, 12, 12, 12)
        self.conversation_layout.setSpacing(12)
        self.conversation_layout.addStretch()
        self.conversation_area.setWidget(self.conversation_container)
        layout.addWidget(self.conversation_area)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Ask Calm Chimp or type /help for commands")
        self.input_line.returnPressed.connect(self.handle_send)
        layout.addWidget(self.input_line)

        controls = QHBoxLayout()
        controls.addStretch()
        self.send_button = QToolButton()
        self.send_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.send_button.clicked.connect(self.handle_send)
        controls.addWidget(self.send_button)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        controls.addWidget(self.status_label)

        layout.addLayout(controls)

        self.setLayout(layout)
        self._append_bot_message("Hello! Use /plan or type /help to see commands.")

    def _append_user_message(self, message: str) -> None:
        self._append_message("user", message)

    def _append_bot_message(
        self,
        message: str,
        details: Optional[str] = None,
        detail_title: Optional[str] = None,
    ) -> None:
        self._append_message("assistant", message, details, detail_title)

    def _append_message(
        self,
        role: str,
        text: str,
        details: Optional[str] = None,
        detail_title: Optional[str] = None,
    ) -> None:
        # remove trailing stretch
        stretch_item = self.conversation_layout.takeAt(self.conversation_layout.count() - 1)

        bubble = ChatMessageWidget(role, text, detail_title, details)
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        if role == "user":
            wrapper_layout.addStretch()
            wrapper_layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignRight)
        else:
            wrapper_layout.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignLeft)
            wrapper_layout.addStretch()

        self.conversation_layout.addWidget(wrapper)
        if stretch_item:
            self.conversation_layout.addItem(stretch_item)

        QApplication.processEvents()
        scrollbar = self.conversation_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def handle_send(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self._append_user_message(text)
        self._set_busy(True)
        try:
            if text.startswith("/"):
                self._handle_command(text)
            else:
                self._handle_freeform(text)
        finally:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.input_line.setDisabled(busy)
        self.send_button.setDisabled(busy)
        icon = (
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
            if busy
            else self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward)
        )
        self.send_button.setIcon(icon)
        self.status_label.setText("Thinking..." if busy else "")
        QApplication.processEvents()

    def _handle_command(self, text: str) -> None:
        if text.lower() in {"/help", "help"}:
            self._append_bot_message(self.HELP_TEXT)
            return
        if text.lower() == "/pending":
            result = call_api("list_pending_tasks_ordered_by_due_date")
            if result["tasks"]:
                lines = "\n".join(f"- {task['title']} (due {task['due_date']})" for task in result["tasks"])
            else:
                lines = "No pending tasks."
            self._append_bot_message(lines)
            return
        if text.lower() == "/overdue":
            result = call_api("list_overdue_tasks")
            if result["tasks"]:
                lines = "\n".join(f"- {task['title']} (due {task['due_date']})" for task in result["tasks"])
            else:
                lines = "No overdue tasks."
            self._append_bot_message(lines)
            return
        if text.lower() == "/today":
            result = call_api("list_tasks_due_today")
            if result["tasks"]:
                lines = "\n".join(f"- {task['title']} ({task['subject']})" for task in result["tasks"])
            else:
                lines = "No tasks due today."
            self._append_bot_message(lines)
            return
        if text.lower() == "/history":
            result = call_api("list_recent_history_actions")
            lines = "\n".join(f"- {entry['timestamp']} {entry['action']}" for entry in result["entries"])
            self._append_bot_message(lines or "No history yet.")
            return
        if text.lower() == "/tools":
            result = call_api("list_available_tools")
            tools = result.get("tools", [])
            if tools:
                summary = f"{len(tools)} tool(s) available."
                details = json.dumps(result, indent=2, ensure_ascii=False)
                self._append_bot_message(summary, details, detail_title="list_available_tools")
            else:
                self._append_bot_message("No tools are currently registered.")
            return
        if text.lower().startswith("/plan"):
            try:
                self._handle_plan_command(text)
            except Exception as exc:  # noqa: BLE001
                self._append_bot_message(f"Could not process plan command: {exc}")
            return

        self._append_bot_message("I did not understand. Type /help for commands.")

    def _handle_plan_command(self, text: str) -> None:
        try:
            payload = text.split(" ", 1)[1]
        except IndexError as exc:  # noqa: BLE001
            raise ValueError("Provide parameters after /plan.") from exc

        parts = {}
        for segment in payload.split(";"):
            if "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            parts[key.strip().lower()] = value.strip()

        subject = parts.get("subject")
        due = parts.get("due")
        hours = float(parts.get("hours", "2.0"))
        outline = parts.get("outline", "")

        if not subject or not due or not outline:
            raise ValueError("subject, due, and outline are required.")

        outline_lines = [line.strip() for line in outline.split("|") if line.strip()]

        result = call_api(
            "generate_plan_from_outline",
            subject=subject,
            due_date=due,
            outline_lines=outline_lines,
            hours_per_section=hours,
        )
        self._append_bot_message(f"Planned {len(result['tasks'])} tasks for {subject}.")
        self.refresher()

    def _handle_freeform(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        orchestration = self.orchestrator.orchestrate(self.history.copy(), text)

        if orchestration.messages:
            for message in orchestration.messages:
                self._append_bot_message(message)
                self.history.append({"role": "assistant", "content": message})

        if orchestration.tool_name:
            try:
                args_details = json.dumps(orchestration.arguments, indent=2, ensure_ascii=False)
                self._append_bot_message(
                    f"I will call `{orchestration.tool_name}` to handle that.",
                    args_details,
                    detail_title=orchestration.tool_name,
                )

                tool_result = call_api(orchestration.tool_name, **orchestration.arguments)
                summary = self._summarize_tool_result(orchestration.tool_name, tool_result)
                detail_payload = json.dumps(
                    {"arguments": orchestration.arguments, "result": tool_result},
                    indent=2,
                    ensure_ascii=False,
                )
                self._append_bot_message(
                    summary,
                    detail_payload,
                    detail_title=f"{orchestration.tool_name} result",
                )
                self.history.append({"role": "assistant", "content": summary})
                focus_date = self._determine_focus_date(orchestration.tool_name, tool_result)
                self.refresher(focus_date)
            except Exception as exc:  # noqa: BLE001
                self._append_bot_message(f"Failed to execute `{orchestration.tool_name}`: {exc}")
        elif not orchestration.messages:
            fallback = "I could not process that request."
            self._append_bot_message(fallback)
            self.history.append({"role": "assistant", "content": fallback})

    def _summarize_tool_result(self, tool_name: str, result: Dict[str, object]) -> str:
        if tool_name.startswith("generate_plan"):
            tasks = result.get("tasks") if isinstance(result, dict) else None
            if isinstance(tasks, list) and tasks:
                first_task = tasks[0]
                subject = first_task.get("subject", "subject")
                due = first_task.get("due_date", "soon")
                return f"Created {len(tasks)} study task(s) for {subject}, due {due}."
            return "Generated a study plan."
        if tool_name == "schedule_meeting":
            task = result.get("task") if isinstance(result, dict) else None
            if isinstance(task, dict):
                title = task.get("title", "Meeting")
                due = task.get("due_date", "scheduled date")
                return f"Scheduled {title} on {due}."
            return "Scheduled the requested meeting."
        if tool_name == "list_available_tools":
            tools = result.get("tools") if isinstance(result, dict) else None
            count = len(tools) if isinstance(tools, list) else 0
            return f"Listed {count} available tool(s)."
        if tool_name.startswith("list_tasks"):
            tasks = result.get("tasks") if isinstance(result, dict) else None
            count = len(tasks) if isinstance(tasks, list) else 0
            return f"Found {count} task(s)."
        if tool_name.startswith("calendar_tasks"):
            tasks = result.get("tasks") if isinstance(result, dict) else None
            count = len(tasks) if isinstance(tasks, list) else 0
            return f"Retrieved {count} calendar entr{ 'y' if count == 1 else 'ies' }."
        if tool_name.startswith("list_recent_history"):
            entries = result.get("entries") if isinstance(result, dict) else None
            count = len(entries) if isinstance(entries, list) else 0
            return f"Listed {count} history entr{ 'y' if count == 1 else 'ies' }."
        return f"`{tool_name}` completed."

    def _determine_focus_date(self, tool_name: str, result: Dict[str, object]) -> Optional[str]:
        if not isinstance(result, dict):
            return None
        if tool_name == "schedule_meeting":
            task = result.get("task")
            if isinstance(task, dict):
                due = task.get("due_date")
                if isinstance(due, str):
                    return due
        if tool_name.startswith("generate_plan"):
            tasks = result.get("tasks")
            if isinstance(tasks, list) and tasks:
                due = tasks[0].get("due_date")
                if isinstance(due, str):
                    return due
        if tool_name in {
            "update_task_due_date",
            "reschedule_task_to_today",
            "reschedule_task_to_tomorrow",
            "reschedule_task_next_week",
        }:
            task = result.get("task")
            if isinstance(task, dict):
                due = task.get("due_date")
                if isinstance(due, str):
                    return due
        return None


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        ensure_data_dir()
        self._build_ui()

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.calendar_tab = CalendarTab(self.refresh_all)
        self.activity_tab = ActivityTab(self.refresh_all)
        self.planner_tab = PlannerTab(self.refresh_all)

        self.tabs.addTab(self.calendar_tab, "Calendar")
        self.tabs.addTab(self.activity_tab, "Recent Activity")
        self.tabs.addTab(self.planner_tab, "Planner")

        left_layout.addWidget(self.tabs)
        left_panel.setLayout(left_layout)

        self.chat_panel = ChatPanel(self.refresh_all)

        splitter.addWidget(left_panel)
        splitter.addWidget(self.chat_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.setCentralWidget(splitter)

        session = get_supabase_session() if supabase_ready() else None
        if session and getattr(session, "user", None):
            email = getattr(session.user, "email", "")
            if email:
                self.statusBar().showMessage(f"Signed in as {email}")

    def refresh_all(self, focus_date: Optional[str] = None) -> None:
        self.calendar_tab.refresh_day(focus_date)
        self.activity_tab.refresh_history()


def run_gui() -> None:
    app = QApplication(sys.argv)
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        QMessageBox.critical(
            None,
            "Supabase configuration missing",
            "Set SUPABASE_URL and SUPABASE_ANON_KEY in your environment to enable Supabase sign-in.",
        )
        sys.exit(1)
    login_dialog = LoginDialog()
    if login_dialog.exec() != int(QDialog.DialogCode.Accepted):
        sys.exit(0)
    window = MainWindow()
    window.resize(1200, 720)
    window.show()
    sys.exit(app.exec())
