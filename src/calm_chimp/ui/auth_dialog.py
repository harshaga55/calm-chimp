from __future__ import annotations

import json
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..core import (
    SUPABASE_ANON_KEY,
    SUPABASE_REDIRECT_PORT,
    SUPABASE_URL,
    SupabaseSettings,
    get_supabase_client,
    initialize_supabase,
    set_supabase_session,
)


class _OAuthCodeListener(BaseHTTPRequestHandler):
    code: Optional[str] = None
    error: Optional[str] = None
    payload: Dict[str, str] = {}
    event = threading.Event()

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        _OAuthCodeListener.code = (query.get("code") or [None])[0]
        _OAuthCodeListener.error = (query.get("error") or [None])[0]
        _OAuthCodeListener.payload = {key: values[0] for key, values in query.items()}
        message = "You can close this window and return to Calm Chimp."
        if _OAuthCodeListener.error:
            message = "Authentication failed. You can close this window."
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode("utf-8"))
        _OAuthCodeListener.event.set()

    def log_message(self, fmt: str, *args):  # noqa: D401
        """Silence handler logging."""


def _reset_oauth_listener() -> None:
    _OAuthCodeListener.code = None
    _OAuthCodeListener.error = None
    _OAuthCodeListener.payload = {}
    _OAuthCodeListener.event.clear()


def _serve_oauth_callback(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _OAuthCodeListener)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _wait_for_oauth_code(timeout: float = 120.0) -> Tuple[Optional[str], Optional[str], Dict[str, str]]:
    _OAuthCodeListener.event.wait(timeout)
    return _OAuthCodeListener.code, _OAuthCodeListener.error, dict(_OAuthCodeListener.payload)


def _find_free_port(preferred_port: int) -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", preferred_port))
            return sock.getsockname()[1]
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]


class LoginDialog(QDialog):
    """PyQt dialog to authenticate against Supabase before launching the main window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Calm Chimp — Sign In")
        self.setModal(True)
        self._ensure_supabase_initialized()
        self.client = get_supabase_client()

        layout = QVBoxLayout(self)
        header = QLabel("Sign in to continue")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(header)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email address")
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)

        button_row = QHBoxLayout()
        email_sign_in = QPushButton("Sign In with Email")
        email_sign_in.clicked.connect(self._sign_in_with_email)
        button_row.addWidget(email_sign_in)

        email_sign_up = QPushButton("Create Account")
        email_sign_up.clicked.connect(self._sign_up_with_email)
        button_row.addWidget(email_sign_up)
        layout.addLayout(button_row)

        google_button = QPushButton("Continue with Google")
        google_button.clicked.connect(self._sign_in_with_google)
        layout.addWidget(google_button)

        cancel_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel_box.rejected.connect(self.reject)
        layout.addWidget(cancel_box)

    # ------------------------------------------------------------------ helpers

    def _ensure_supabase_initialized(self) -> None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            raise RuntimeError(
                "Supabase credentials are missing. Set SUPABASE_URL and SUPABASE_ANON_KEY in the environment."
            )
        initialize_supabase(SupabaseSettings(url=SUPABASE_URL, anon_key=SUPABASE_ANON_KEY))

    def _set_status(self, message: str, *, is_error: bool = False) -> None:
        color = "#c62828" if is_error else "#2e7d32"
        self.status_label.setStyleSheet(f"color: {color};")
        self.status_label.setText(message)

    def _collect_email_credentials(self) -> Tuple[str, str]:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            raise ValueError("Provide both email and password.")
        return email, password

    # ------------------------------------------------------------------ handlers

    def _sign_in_with_email(self) -> None:
        try:
            email, password = self._collect_email_credentials()
        except ValueError as exc:
            self._set_status(str(exc), is_error=True)
            return
        try:
            response = self.client.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Email sign-in failed: {exc}", is_error=True)
            return
        session = getattr(response, "session", None)
        if session is None:
            self._set_status("Check your email for a verification link to finish sign-in.")
            return
        set_supabase_session(session)
        self.accept()

    def _sign_up_with_email(self) -> None:
        try:
            email, password = self._collect_email_credentials()
        except ValueError as exc:
            self._set_status(str(exc), is_error=True)
            return
        try:
            response = self.client.auth.sign_up({"email": email, "password": password})
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Sign-up failed: {exc}", is_error=True)
            return
        user = getattr(response, "user", None)
        if user is None:
            self._set_status("Check your inbox to confirm your email before signing in.")
            return
        self._set_status("Account created. Please verify your email if required, then sign in.", is_error=False)

    def _sign_in_with_google(self) -> None:
        port = _find_free_port(SUPABASE_REDIRECT_PORT)
        redirect_url = f"http://localhost:{port}/auth/callback"
        _reset_oauth_listener()
        server = _serve_oauth_callback(port)
        try:
            response = self.client.auth.sign_in_with_oauth(
                {"provider": "google", "options": {"redirect_to": redirect_url}}
            )
        except Exception as exc:  # noqa: BLE001
            server.shutdown()
            self._set_status(f"Google sign-in failed: {exc}", is_error=True)
            return

        auth_url = getattr(response, "url", None)
        if not auth_url:
            server.shutdown()
            self._set_status("Supabase did not return an OAuth URL.", is_error=True)
            return

        webbrowser.open(auth_url, new=1, autoraise=True)

        code, error, payload = _wait_for_oauth_code()
        server.shutdown()

        if error:
            self._set_status(f"Google sign-in error: {error}", is_error=True)
            return
        if not code:
            self._set_status("Login timed out. Please try again.", is_error=True)
            return

        try:
            exchange = self.client.auth.exchange_code_for_session(
                {"auth_code": code, "provider": "google", "redirect_to": redirect_url}
            )
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed to exchange Google code: {exc}", is_error=True)
            return

        session = getattr(exchange, "session", None)
        if session is None:
            details = json.dumps(payload, indent=2) if payload else "unknown reason"
            self._set_status(f"Google login incomplete: {details}", is_error=True)
            return

        set_supabase_session(session)
        self.accept()
