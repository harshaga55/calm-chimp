from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...domain import UserProfile
from ..supabase import SupabaseGateway


@dataclass(slots=True)
class ProfileRepository:
    gateway: SupabaseGateway
    table_name: str

    def fetch(self, user_id: str) -> Optional[UserProfile]:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return UserProfile.from_record(response.data)

    def upsert(self, profile: UserProfile) -> UserProfile:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .upsert(
                {
                    "id": profile.id,
                    "email": profile.email,
                    "full_name": profile.full_name,
                    "avatar_url": profile.avatar_url,
                },
                on_conflict="id",
            )
            .select("*")
            .single()
            .execute()
        )
        return UserProfile.from_record(response.data or {"id": profile.id, "email": profile.email})
