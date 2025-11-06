from __future__ import annotations

import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout

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
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 32)
        layout.setSpacing(16)
        layout.addStretch(1)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(24)

        hero = QVBoxLayout()
        hero.setSpacing(6)
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header = QLabel("Welcome back")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(header)

        subtitle = QLabel("Sign in to Sync Supabase Events")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(subtitle)

        blurb = QLabel("Connect Calm Chimp to your Supabase workspace to keep calendars and tasks perfectly in sync.")
        blurb.setObjectName("caption")
        blurb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        blurb.setWordWrap(True)
        hero.addWidget(blurb)
        card_layout.addLayout(hero)

        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignHCenter)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(14)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@example.com")
        self.email_input.setClearButtonEnabled(True)
        self.email_input.returnPressed.connect(self._sign_in)
        self.email_input.textChanged.connect(self._clear_status)
        form.addRow("Email", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setClearButtonEnabled(True)
        self.password_input.returnPressed.connect(self._sign_in)
        self.password_input.textChanged.connect(self._clear_status)
        form.addRow("Password", self.password_input)
        card_layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        card_layout.addWidget(self.status_label)

        actions = QVBoxLayout()
        actions.setSpacing(12)

        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)

        login_btn = QPushButton("Sign In")
        login_btn.setObjectName("primaryButton")
        login_btn.setDefault(True)
        login_btn.clicked.connect(self._sign_in)
        login_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        primary_row.addWidget(login_btn)

        signup_btn = QPushButton("Create Account")
        signup_btn.setObjectName("secondaryButton")
        signup_btn.clicked.connect(self._sign_up)
        signup_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        primary_row.addWidget(signup_btn)
        actions.addLayout(primary_row)

        divider_row = QHBoxLayout()
        divider_row.setSpacing(8)
        divider_row.setContentsMargins(0, 6, 0, 6)

        divider_left = QFrame()
        divider_left.setObjectName("divider")
        divider_left.setFrameShape(QFrame.Shape.NoFrame)
        divider_left.setFixedHeight(1)
        divider_row.addWidget(divider_left)

        divider_label = QLabel("or")
        divider_label.setObjectName("muted")
        divider_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        divider_row.addWidget(divider_label)

        divider_right = QFrame()
        divider_right.setObjectName("divider")
        divider_right.setFrameShape(QFrame.Shape.NoFrame)
        divider_right.setFixedHeight(1)
        divider_row.addWidget(divider_right)
        divider_row.setStretch(0, 1)
        divider_row.setStretch(2, 1)
        actions.addLayout(divider_row)

        google_btn = QPushButton("Continue with Google")
        google_btn.setObjectName("googleButton")
        google_btn.clicked.connect(self._sign_in_google)
        google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        google_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        actions.addWidget(google_btn)
        card_layout.addLayout(actions)

        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        footer.addWidget(cancel)
        layout.addLayout(footer)

        self._action_buttons = [login_btn, signup_btn, google_btn]
        self._status_kind = "info"
        self._default_status = "Enter your Supabase credentials to continue."
        self._set_status(self._default_status)
        self.email_input.setFocus()

    # ------------------------------------------------------------------ helpers

    def _set_status(self, message: str, *, kind: str = "info") -> None:
        self._status_kind = kind
        if not message:
            self.status_label.hide()
            return

        styles = {
            "info": ("#cbd5f5", "#1a283d", "#273852"),
            "success": ("#70e000", "#17321c", "#275d30"),
            "error": ("#ef233c", "#3a181f", "#55202c"),
        }
        color, background, border = styles.get(kind, styles["info"])
        stylesheet = (
            f"color: {color};"
            f"background-color: {background};"
            f"border: 1px solid {border};"
            "padding: 8px 12px;"
            "border-radius: 6px;"
        )
        self.status_label.setStyleSheet(stylesheet)
        self.status_label.setText(message)
        self.status_label.show()

    def _clear_status(self) -> None:
        if getattr(self, "_status_kind", "") == "error":
            self._set_status(self._default_status)

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.email_input, self.password_input, *self._action_buttons):
            widget.setEnabled(not busy)

    def _credentials(self) -> Tuple[str, str]:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            raise ValueError("Email and password are required.")
        return email, password

    def _handle_error(self, exc: Exception) -> None:
        self._set_busy(False)
        self._set_status(str(exc), kind="error")

    def _finish_sign_in(self, _response: object) -> None:
        self._set_busy(False)
        if not self.auth_service.context.gateway.is_ready():
            self._set_status("Authentication incomplete. Check your inbox for verification.", kind="error")
            return
        self._set_status("Authentication successful.", kind="success")
        self.accept()

    # ------------------------------------------------------------------ slots

    def _sign_in(self) -> None:
        try:
            email, password = self._credentials()
        except ValueError as exc:
            self._set_status(str(exc), kind="error")
            return
        self._set_busy(True)
        self._set_status("Signing you in...", kind="info")

        def worker() -> object:
            return self.auth_service.sign_in_with_password(email, password)

        self.runner.submit(worker, on_success=self._finish_sign_in, on_error=self._handle_error)

    def _sign_up(self) -> None:
        try:
            email, password = self._credentials()
        except ValueError as exc:
            self._set_status(str(exc), kind="error")
            return
        self._set_busy(True)
        self._set_status("Creating your account...", kind="info")

        def worker() -> object:
            return self.auth_service.sign_up_with_password(email, password)

        def done(_result: object) -> None:
            self._set_busy(False)
            self._set_status("Account created. Please verify your email then sign in.", kind="success")

        self.runner.submit(worker, on_success=done, on_error=self._handle_error)

    def _sign_in_google(self) -> None:
        if not self.supabase_settings.is_configured:
            self._set_status("Supabase credentials missing. Set SUPABASE_URL and SUPABASE_ANON_KEY.", kind="error")
            return
        port = _find_port(self.supabase_settings.redirect_port)
        redirect_url = f"http://localhost:{port}/auth/callback"
        server = _start_oauth_server(port)
        _reset_oauth_state()
        self._set_status("Waiting for Google OAuth...", kind="info")

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
