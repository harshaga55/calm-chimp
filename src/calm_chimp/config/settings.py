from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LlmSettings:
    api_key: Optional[str]
    model: str
    base_url: Optional[str]
    api_version: Optional[str]
    organization: Optional[str]
    project: Optional[str]

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    @property
    def missing_env_vars(self) -> list[str]:
        missing = []
        if not self.api_key:
            missing.append("OPENAI_API_KEY")
        if not self.model:
            missing.append("OPENAI_MODEL")
        return missing


@dataclass(frozen=True)
class SupabaseSettings:
    url: Optional[str]
    anon_key: Optional[str]
    redirect_host: str
    redirect_port: int

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.anon_key)

    @property
    def redirect_url(self) -> str:
        return f"http://{self.redirect_host}:{self.redirect_port}/auth/callback"


@dataclass(frozen=True)
class CacheSettings:
    window_before: timedelta
    window_after: timedelta
    max_results: int
    refresh_interval: timedelta


@dataclass(frozen=True)
class UiSettings:
    app_name: str
    organization: str
    timezone: str


@dataclass(frozen=True)
class StorageSettings:
    events_table: str
    categories_table: str
    profiles_table: str


@dataclass(frozen=True)
class AppSettings:
    llm: LlmSettings
    supabase: SupabaseSettings
    cache: CacheSettings
    ui: UiSettings
    storage: StorageSettings


def _timedelta_from_env(name: str, default_days: int) -> timedelta:
    raw = os.getenv(name)
    if not raw:
        return timedelta(days=default_days)
    try:
        days = float(raw)
    except ValueError:
        return timedelta(days=default_days)
    return timedelta(days=days)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    llm = LlmSettings(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-5.2"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_version=os.getenv("OPENAI_API_VERSION"),
        organization=os.getenv("OPENAI_ORG"),
        project=os.getenv("OPENAI_PROJECT"),
    )

    supabase = SupabaseSettings(
        url=os.getenv("SUPABASE_URL"),
        anon_key=os.getenv("SUPABASE_ANON_KEY"),
        redirect_host=os.getenv("SUPABASE_REDIRECT_HOST", "127.0.0.1"),
        redirect_port=int(os.getenv("SUPABASE_REDIRECT_PORT", "52151")),
    )

    cache = CacheSettings(
        window_before=_timedelta_from_env("CALM_CACHE_WINDOW_BEFORE_DAYS", 365),
        window_after=_timedelta_from_env("CALM_CACHE_WINDOW_AFTER_DAYS", 365),
        max_results=int(os.getenv("CALM_CACHE_MAX_RESULTS", "5000")),
        refresh_interval=timedelta(seconds=int(os.getenv("CALM_CACHE_REFRESH_SECONDS", "90"))),
    )

    ui = UiSettings(
        app_name=os.getenv("CALM_APP_NAME", "Calm Chimp"),
        organization=os.getenv("CALM_APP_ORG", "CalmChimp"),
        timezone=os.getenv("CALM_APP_TIMEZONE", "UTC"),
    )

    storage = StorageSettings(
        events_table=os.getenv("SUPABASE_EVENTS_TABLE", "calendar_events"),
        categories_table=os.getenv("SUPABASE_CATEGORIES_TABLE", "event_categories"),
        profiles_table=os.getenv("SUPABASE_PROFILES_TABLE", "profiles"),
    )

    return AppSettings(llm=llm, supabase=supabase, cache=cache, ui=ui, storage=storage)
