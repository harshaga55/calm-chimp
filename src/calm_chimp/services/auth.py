from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .context import ServiceContext


@dataclass(slots=True)
class AuthService:
    context: ServiceContext

    def _client(self):
        return self.context.gateway.ensure_client()

    def sign_in_with_password(self, email: str, password: str) -> Any:
        response = self._client().auth.sign_in_with_password({"email": email, "password": password})
        session = getattr(response, "session", None)
        if session:
            self.context.gateway.set_session(session)
            self.context.cache.clear()
        return response

    def sign_up_with_password(self, email: str, password: str) -> Any:
        return self._client().auth.sign_up({"email": email, "password": password})

    def sign_in_with_oauth(self, provider: str, *, redirect_to: str) -> Any:
        return self._client().auth.sign_in_with_oauth({"provider": provider, "options": {"redirect_to": redirect_to}})

    def exchange_code_for_session(self, code: str) -> Optional[Any]:
        response = self._client().auth.exchange_code_for_session({"code": code})
        session = getattr(response, "session", None)
        if session:
            self.context.gateway.set_session(session)
            self.context.cache.clear()
        return session

    def set_session(self, session: Any) -> None:
        self.context.gateway.set_session(session)
        self.context.cache.clear()

    def current_session(self) -> Any:
        return self.context.gateway.session()

    def sign_out(self) -> None:
        try:
            self._client().auth.sign_out()
        finally:
            self.context.gateway.clear_session()
            self.context.cache.clear()
