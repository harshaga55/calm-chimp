from __future__ import annotations

import json
import os
from pathlib import Path
from platformdirs import user_data_dir

APP_NAME = "Calm Chimp"
APP_AUTHOR = "CalmChimp"
DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR))
DATABASE_FILE = DATA_DIR / "tasks.json"
DEFAULT_DATABASE_CONTENT = {
    "tasks": [],
    "subjects": [],
    "history": [],
    "metadata": {"schema_version": 1},
}

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_REDIRECT_PORT = int(os.getenv("SUPABASE_REDIRECT_PORT", "52151"))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATABASE_FILE.exists():
        DATABASE_FILE.write_text(
            json.dumps(DEFAULT_DATABASE_CONTENT, indent=2) + "\n",
            encoding="utf-8",
        )
