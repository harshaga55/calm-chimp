from __future__ import annotations

import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import Qt, QRectF, QSize, QPointF
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor

from ..assets import asset_path
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


def _google_icon(size: int = 22) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    thickness = max(3, size // 5)
    pen = QPen()
    pen.setWidth(thickness)
    rect = QRectF(thickness, thickness, size - thickness * 2, size - thickness * 2)
    arcs = [
        ("#4285F4", 300, 110),
        ("#EA4335", 30, 110),
        ("#FBBC05", 140, 100),
        ("#34A853", 230, 100),
    ]
    for color, start, span in arcs:
        pen.setColor(QColor(color))
        painter.setPen(pen)
        painter.drawArc(rect, int(start * 16), int(span * 16))
    pen.setColor(QColor("#4285F4"))
    painter.setPen(pen)
    center = rect.center()
    painter.drawLine(center, QPointF(rect.right(), center.y()))
    painter.end()
    return QIcon(pix)


class LoginDialog(QDialog):
    def __init__(self, *, auth_service: AuthService, supabase_settings: SupabaseSettings) -> None:
        super().__init__()
        self.setObjectName("loginDialog")
        self.auth_service = auth_service
        self.supabase_settings = supabase_settings
        self.runner = TaskRunner()

        self.setWindowTitle("Calm Chimp — Sign in")
        self.setModal(True)
        self.setMinimumSize(640, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        shell = QFrame()
        shell.setObjectName("loginShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(24, 24, 24, 24)
        shell_layout.setSpacing(10)

        form_card = QFrame()
        form_card.setObjectName("loginForm")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(28, 32, 28, 28)
        form_layout.setSpacing(12)

        logo_badge = QFrame()
        logo_badge.setObjectName("logoBadge")
        logo_badge_layout = QVBoxLayout(logo_badge)
        logo_badge_layout.setContentsMargins(12, 12, 12, 12)
        logo_badge_layout.setSpacing(6)

        logo = QLabel()
        logo.setObjectName("brandLogo")
        logo_pix = QPixmap(asset_path("branding/calm-chimp-logo.webp"))
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_badge_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        app_name = QLabel("Calm Chimp")
        app_name.setObjectName("brandName")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_badge_layout.addWidget(app_name)

        app_tagline = QLabel("Calendar-native workspace with human-friendly AI.")
        app_tagline.setObjectName("brandTagline")
        app_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        app_tagline.setWordWrap(True)
        logo_badge_layout.addWidget(app_tagline)

        form_layout.addWidget(logo_badge, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Welcome to Calm Chimp")
        title.setObjectName("heroTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(title)

        subtitle = QLabel(
            "Keep your calendar organized with a focused workspace.\n"
            "Plan tasks alongside events with clear, split-pane views.\n"
            "AI helps summarize days without taking over your agenda.\n"
            "Your data stays private; revoke access whenever you want.\n"
            "Continue with Google to sign in securely."
        )
        subtitle.setObjectName("heroSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        form_layout.addWidget(subtitle)

        form_layout.addItem(QSpacerItem(0, 4))

        pill_row = QFrame()
        pill_row.setObjectName("pillRow")
        pill_layout = QHBoxLayout(pill_row)
        pill_layout.setContentsMargins(6, 6, 6, 6)
        pill_layout.setSpacing(8)
        for pill_text in ("OAuth2 secured", "No inbox access", "Sign out anytime"):
            pill = QLabel(pill_text)
            pill.setObjectName("featurePill")
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill_layout.addWidget(pill)
        form_layout.addWidget(pill_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        form_layout.addWidget(self.status_label)

        google_btn = QPushButton("Continue with Google")
        google_btn.setObjectName("googleButton")
        google_btn.clicked.connect(self._sign_in_google)
        google_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        google_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        google_btn.setIcon(_google_icon())
        google_btn.setIconSize(QSize(20, 20))
        form_layout.addWidget(google_btn)

        form_layout.addStretch(1)
        shell_layout.addStretch(1)
        shell_layout.addWidget(form_card, alignment=Qt.AlignmentFlag.AlignCenter)
        shell_layout.addStretch(1)
        layout.addWidget(shell)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        footer.addWidget(cancel)
        layout.addLayout(footer)

        self._action_buttons = [google_btn]
        self._status_kind = "info"
        self._default_status = "Continue with Google to connect your cloud workspace."
        self._set_status(self._default_status)
        google_btn.setFocus()

    # ------------------------------------------------------------------ helpers

    def _set_status(self, message: str, *, kind: str = "info") -> None:
        self._status_kind = kind
        if not message:
            self.status_label.hide()
            return

        styles = {
            "info": ("#e0e7ff", "#111a2e", "#1f2a44"),
            "success": ("#4ade80", "#11261a", "#1f3d29"),
            "error": ("#f87171", "#2e1114", "#4e1c22"),
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

    def _set_busy(self, busy: bool) -> None:
        for widget in self._action_buttons:
            widget.setEnabled(not busy)

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
