from __future__ import annotations

import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..config.settings import SupabaseSettings
from ..services import AuthService
from ..utils.qt import TaskRunner


class _OAuthHandler(BaseHTTPRequestHandler):
    code: Optional[str] = None
    error: Optional[str] = None
    event = threading.Event()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        _OAuthHandler.code = (params.get("code") or [None])[0]
        _OAuthHandler.error = (params.get("error") or [None])[0]
        message = "Authentication complete. You may close this window." if not _OAuthHandler.error else "Authentication failed."
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode("utf-8"))
        _OAuthHandler.event.set()

    def log_message(self, fmt: str, *args):  # noqa: D401
        """Silence default request logging."""


def _reset_oauth_state() -> None:
    _OAuthHandler.code = None
    _OAuthHandler.error = None
    _OAuthHandler.event.clear()


def _find_port(preferred: int) -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", preferred))
            return sock.getsockname()[1]
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


def _start_oauth_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _OAuthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class LoginDialog(QDialog):
    def __init__(self, *, auth_service: AuthService, supabase_settings: SupabaseSettings) -> None:
        super().__init__()
        self.auth_service = auth_service
        self.supabase_settings = supabase_settings
        self.runner = TaskRunner()

        self.setWindowTitle("Calm Chimp — Sign in")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        header = QLabel("Welcome back")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("Sign in to Sync Supabase Events")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        form = QFormLayout()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        form.addRow("Email", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password", self.password_input)
        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons_row = QGridLayout()
        login_btn = QPushButton("Sign In")
        login_btn.clicked.connect(self._sign_in)
        buttons_row.addWidget(login_btn, 0, 0)

        signup_btn = QPushButton("Create Account")
        signup_btn.clicked.connect(self._sign_up)
        buttons_row.addWidget(signup_btn, 0, 1)

        google_btn = QPushButton("Continue with Google")
        google_btn.clicked.connect(self._sign_in_google)
        buttons_row.addWidget(google_btn, 1, 0, 1, 2)
        layout.addLayout(buttons_row)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        footer.addWidget(cancel)
        layout.addLayout(footer)

        self._set_status("Enter your Supabase credentials to continue.")

    # ------------------------------------------------------------------ helpers

    def _set_status(self, message: str, *, error: bool = False) -> None:
        color = "#ef233c" if error else "#70e000"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.email_input, self.password_input):
            widget.setEnabled(not busy)

    def _credentials(self) -> Tuple[str, str]:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            raise ValueError("Email and password are required.")
        return email, password

    def _handle_error(self, exc: Exception) -> None:
        self._set_busy(False)
        self._set_status(str(exc), error=True)

    def _finish_sign_in(self, _response: object) -> None:
        self._set_busy(False)
        if not self.auth_service.context.gateway.is_ready():
            self._set_status("Authentication incomplete. Check your inbox for verification.", error=True)
            return
        self._set_status("Authentication successful.")
        self.accept()

    # ------------------------------------------------------------------ slots

    def _sign_in(self) -> None:
        try:
            email, password = self._credentials()
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._set_busy(True)

        def worker() -> object:
            return self.auth_service.sign_in_with_password(email, password)

        self.runner.submit(worker, on_success=self._finish_sign_in, on_error=self._handle_error)

    def _sign_up(self) -> None:
        try:
            email, password = self._credentials()
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return
        self._set_busy(True)

        def worker() -> object:
            return self.auth_service.sign_up_with_password(email, password)

        def done(_result: object) -> None:
            self._set_busy(False)
            self._set_status("Account created. Please verify your email then sign in.")

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def _sign_in_google(self) -> None:
        if not self.supabase_settings.is_configured:
            self._set_status("Supabase credentials missing. Set SUPABASE_URL and SUPABASE_ANON_KEY.", error=True)
            return
        port = _find_port(self.supabase_settings.redirect_port)
        redirect_url = f"http://localhost:{port}/auth/callback"
        server = _start_oauth_server(port)
        _reset_oauth_state()
        self._set_status("Waiting for Google OAuth...")

        def worker() -> object:
            response = self.auth_service.sign_in_with_oauth("google", redirect_to=redirect_url)
            url = getattr(response, "url", None)
            if url:
                webbrowser.open(url)
            _OAuthHandler.event.wait(timeout=120)
            if _OAuthHandler.error:
                raise RuntimeError(_OAuthHandler.error)
            if not _OAuthHandler.code:
                raise RuntimeError("No OAuth code received.")
            session = self.auth_service.exchange_code_for_session(_OAuthHandler.code)
            if session is None:
                raise RuntimeError("Failed to exchange OAuth code for session.")
            return session

        def finalize(result: object) -> None:
            server.shutdown()
            self._finish_sign_in(result)

        def fail(exc: Exception) -> None:
            server.shutdown()
            self._handle_error(exc)

        self.runner.submit(worker, on_success=finalize, on_error=fail)
