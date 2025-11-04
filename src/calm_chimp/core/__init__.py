"""Core domain models, configuration, and persistence utilities."""

from .config import (
    APP_NAME,
    DATA_DIR,
    DATABASE_FILE,
    DEFAULT_DATABASE_CONTENT,
    SUPABASE_ANON_KEY,
    SUPABASE_REDIRECT_PORT,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
    ensure_data_dir,
)
from .database import JsonDatabase, SupabaseDatabase
from .models import HistoryEntry, StudySubject, StudyTask
from .supabase_client import (
    SupabaseNotConfiguredError,
    SupabaseSessionMissingError,
    SupabaseSettings,
    clear_supabase_session,
    current_user_id,
    get_supabase_client,
    get_supabase_session,
    initialize_supabase,
    set_supabase_session,
    supabase_ready,
)
from .scheduler import distribute_plan

__all__ = [
    "APP_NAME",
    "DATA_DIR",
    "DATABASE_FILE",
    "JsonDatabase",
    "SupabaseDatabase",
    "StudySubject",
    "StudyTask",
    "HistoryEntry",
    "ensure_data_dir",
    "distribute_plan",
    "DEFAULT_DATABASE_CONTENT",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_REDIRECT_PORT",
    "SupabaseSettings",
    "initialize_supabase",
    "get_supabase_client",
    "get_supabase_session",
    "set_supabase_session",
    "clear_supabase_session",
    "current_user_id",
    "SupabaseNotConfiguredError",
    "SupabaseSessionMissingError",
    "supabase_ready",
]
