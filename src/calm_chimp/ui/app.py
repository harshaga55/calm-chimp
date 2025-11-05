from __future__ import annotations

import sys
from PyQt6.QtWidgets import QApplication

from ..api import api_state
from ..bootstrap import configure_logging
from ..config import AppPalette, get_settings
from .login import LoginDialog
from .main_window import MainWindow
from .styles.theme import apply_palette


def run_gui() -> None:
    configure_logging()
    app = QApplication.instance() or QApplication(sys.argv)
    settings = get_settings()
    apply_palette(app, AppPalette())

    login = LoginDialog(auth_service=api_state.auth, supabase_settings=settings.supabase)
    if login.exec() != LoginDialog.DialogCode.Accepted:
        return

    window = MainWindow(api_state=api_state, settings=settings)
    window.show()
    sys.exit(app.exec())
