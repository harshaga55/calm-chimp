from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from supabase import Client, create_client

from ..config.settings import SupabaseSettings


class SupabaseNotInitializedError(RuntimeError):
    """Raised when accessing the Supabase client before initialization."""


class SupabaseSessionMissingError(RuntimeError):
    """Raised when a session-specific action is attempted without a session."""


@dataclass
class SupabaseGateway:
    """Thin wrapper around the Supabase Python client with session awareness."""

    settings: SupabaseSettings
    _client: Optional[Client] = None
    _session: Optional[Any] = None

    def ensure_client(self) -> Client:
        if self._client is not None:
            return self._client
        if not self.settings.is_configured:
            raise SupabaseNotInitializedError("Supabase settings are missing URL or anon key.")
        self._client = create_client(self.settings.url, self.settings.anon_key)
        return self._client

    def client(self) -> Client:
        if self._client is None:
            raise SupabaseNotInitializedError("Supabase client has not been initialized. Call ensure_client() first.")
        return self._client

    def set_session(self, session: Any) -> None:
        self._session = session

    def clear_session(self) -> None:
        self._session = None

    def session(self) -> Any:
        if self._session is None:
            raise SupabaseSessionMissingError("Supabase session is not available.")
        return self._session

    def current_user_id(self) -> str:
        session = self.session()
        user = getattr(session, "user", None)
        identifier = getattr(user, "id", None)
        if not identifier:
            raise SupabaseSessionMissingError("Supabase session has no user id.")
        return identifier

    def is_ready(self) -> bool:
        return self._client is not None and self._session is not None

    def table(self, name: str):
        return self.ensure_client().table(name)
