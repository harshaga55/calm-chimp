from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QCalendarWidget,
)

from ..api import call_api
from ..core import APP_NAME, ensure_data_dir


class CalendarTab(QWidget):
    def __init__(self, refresher: Callable[[], None]) -> None:
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

    def refresh_day(self) -> None:
        day = self._selected_date()
        result = call_api("calendar_tasks_for_day", day=day)
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
    def __init__(self, refresher: Callable[[], None]) -> None:
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
    def __init__(self, refresher: Callable[[], None]) -> None:
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


class ChatPanel(QWidget):
    HELP_TEXT = (
        "Commands:\n"
        "/plan subject=<name>;due=<YYYY-MM-DD>;hours=<float>;outline=line1|line2\n"
        "/pending – list pending tasks\n"
        "/overdue – list overdue tasks\n"
        "/today – list tasks due today\n"
        "/history – show recent history"
    )

    def __init__(self, refresher: Callable[[], None]) -> None:
        super().__init__()
        self.refresher = refresher
        layout = QVBoxLayout()

        self.conversation = QTextEdit()
        self.conversation.setReadOnly(True)
        layout.addWidget(self.conversation)

        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Type a command, e.g., /plan subject=... ")
        layout.addWidget(self.input_line)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self.handle_send)
        layout.addWidget(send_button)

        self.setLayout(layout)
        self._append_bot_message("Hello! Use /plan or type /help to see commands.")

    def _append_user_message(self, message: str) -> None:
        self.conversation.append(f"<b>You:</b> {message}")
        self.conversation.moveCursor(QTextCursor.MoveOperation.End)

    def _append_bot_message(self, message: str) -> None:
        self.conversation.append(f"<b>Calm Chimp:</b> {message}")
        self.conversation.moveCursor(QTextCursor.MoveOperation.End)

    def handle_send(self) -> None:
        text = self.input_line.text().strip()
        if not text:
            return
        self.input_line.clear()
        self._append_user_message(text)
        self._handle_command(text)

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

    def refresh_all(self) -> None:
        self.calendar_tab.refresh_day()
        self.activity_tab.refresh_history()


def run_gui() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 720)
    window.show()
    sys.exit(app.exec())
