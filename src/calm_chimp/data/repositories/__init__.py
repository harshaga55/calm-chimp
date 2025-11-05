"""Supabase repositories for first-class domain objects."""

from __future__ import annotations

from .events import EventRepository
from .categories import CategoryRepository
from .profiles import ProfileRepository

__all__ = ["CategoryRepository", "EventRepository", "ProfileRepository"]
