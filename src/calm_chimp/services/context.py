from __future__ import annotations

from dataclasses import dataclass, field

from ..config import AppSettings, get_settings
from ..data import SupabaseGateway, TimelineCache
from ..data.repositories import CategoryRepository, EventRepository, ProfileRepository


@dataclass(slots=True)
class ServiceContext:
    """Aggregate root for services to share settings, gateway, and caches."""

    settings: AppSettings = field(default_factory=get_settings)
    gateway: SupabaseGateway = field(init=False)
    events: EventRepository = field(init=False)
    categories: CategoryRepository = field(init=False)
    profiles: ProfileRepository = field(init=False)
    cache: TimelineCache = field(init=False)

    def __post_init__(self) -> None:
        self.gateway = SupabaseGateway(self.settings.supabase)
        self.cache = TimelineCache(
            window_before=self.settings.cache.window_before,
            window_after=self.settings.cache.window_after,
            max_results=self.settings.cache.max_results,
        )
        self.events = EventRepository(
            gateway=self.gateway,
            table_name=self.settings.storage.events_table,
            categories_table=self.settings.storage.categories_table,
        )
        self.categories = CategoryRepository(
            gateway=self.gateway,
            table_name=self.settings.storage.categories_table,
        )
        self.profiles = ProfileRepository(
            gateway=self.gateway,
            table_name=self.settings.storage.profiles_table,
        )
