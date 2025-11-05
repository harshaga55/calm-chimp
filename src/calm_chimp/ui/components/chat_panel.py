from __future__ import annotations

import json
import html
from typing import Any, Dict, List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ...orchestrator import LangGraphOrchestrator
from ...utils.qt import TaskRunner


class ChatPanel(QWidget):
    tool_executed = pyqtSignal(str, dict, dict)

    def __init__(self, *, orchestrator: LangGraphOrchestrator, runner: TaskRunner) -> None:
        super().__init__()
        self.orchestrator = orchestrator
        self.runner = runner
        self.history: List[Dict[str, str]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Ask the Calm Chimp assistant to plan or summarize events...")
        layout.addWidget(self.transcript)

        input_row = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Type a question or /help")
        self.input_line.returnPressed.connect(self._send)
        input_row.addWidget(self.input_line)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self._send)
        input_row.addWidget(send_button)
        layout.addLayout(input_row)

    def append_message(self, role: str, content: str) -> None:
        prefix = "You" if role == "user" else "Assistant"
        self.transcript.append(f"<b>{prefix}:</b> {content}")

    def _send(self) -> None:
        message = self.input_line.text().strip()
        if not message:
            return
        self.input_line.clear()
        self.append_message("user", message)
        self.history.append({"role": "user", "content": message})
        self.input_line.setEnabled(False)

        def worker() -> Dict[str, Any]:
            return self.orchestrator.invoke(self.history, message)

        def done(result: Dict[str, Any]) -> None:
            self.input_line.setEnabled(True)
            messages = result.get("messages", [])
            for text in messages:
                self.append_message("assistant", text)
                self.history.append({"role": "assistant", "content": text})
            tool_name = result.get("tool_name")
            if tool_name:
                arguments = result.get("arguments", {})
                output = result.get("tool_output", {})
                if output:
                    pretty = html.escape(json.dumps(output, indent=2))
                else:
                    pretty = "No data returned."
                self.append_message("assistant", f"`{tool_name}` result:<br><pre>{pretty}</pre>")
                self.tool_executed.emit(tool_name, arguments, output or {})

        def fail(exc: Exception) -> None:
            self.input_line.setEnabled(True)
            self.append_message("assistant", f"Error: {exc}")

        self.runner.submit(worker, on_success=done, on_error=fail)
