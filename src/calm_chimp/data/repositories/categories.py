from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...domain import Category
from ..supabase import SupabaseGateway


@dataclass(slots=True)
class CategoryRepository:
    gateway: SupabaseGateway
    table_name: str

    def list_for_user(self, user_id: str) -> list[Category]:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .select("*")
            .eq("user_id", user_id)
            .order("name")
            .execute()
        )
        records = response.data or []
        return [Category.from_record(record) for record in records]

    def upsert(self, category: Category) -> Category:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .upsert(category.to_record(), on_conflict="id")
            .select("*")
            .single()
            .execute()
        )
        return Category.from_record(response.data or category.to_record())

    def delete(self, category_id: str) -> bool:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .delete()
            .eq("id", category_id)
            .execute()
        )
        deleted = response.data or []
        return bool(deleted)

    def fetch(self, category_id: str) -> Category | None:
        response = (
            self.gateway.ensure_client()
            .table(self.table_name)
            .select("*")
            .eq("id", category_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return Category.from_record(response.data)
