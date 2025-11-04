from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from supabase import Client, create_client

_client: Optional[Client] = None
_session: Optional[Any] = None


class SupabaseNotConfiguredError(RuntimeError):
    """Raised when Supabase has not been initialized before use."""


class SupabaseSessionMissingError(RuntimeError):
    """Raised when a Supabase session-dependent call executes without a session."""


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    anon_key: str


def initialize_supabase(settings: SupabaseSettings) -> Client:
    global _client
    _client = create_client(settings.url, settings.anon_key)
    return _client


def get_supabase_client() -> Client:
    if _client is None:
        raise SupabaseNotConfiguredError("Supabase client has not been initialized.")
    return _client


def set_supabase_session(session: Any) -> None:
    global _session
    _session = session


def clear_supabase_session() -> None:
    global _session
    _session = None


def get_supabase_session() -> Any:
    if _session is None:
        raise SupabaseSessionMissingError("Supabase session is not available.")
    return _session


def current_user_id() -> str:
    session = get_supabase_session()
    user = getattr(session, "user", None)
    if user is None:
        raise SupabaseSessionMissingError("Active Supabase session has no user.")
    identifier = getattr(user, "id", None)
    if not identifier:
        raise SupabaseSessionMissingError("Supabase user identifier is missing.")
    return identifier


def supabase_ready() -> bool:
    return _client is not None and _session is not None
