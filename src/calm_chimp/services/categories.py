from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from ..domain import Category
from .context import ServiceContext


@dataclass(slots=True)
class CategoryService:
    context: ServiceContext

    def list_categories(self) -> list[Category]:
        user_id = self.context.gateway.current_user_id()
        return self.context.categories.list_for_user(user_id)

    def upsert_category(
        self,
        *,
        category_id: Optional[str],
        name: str,
        color: Optional[str] = None,
        icon: Optional[str] = None,
        description: str = "",
    ) -> Category:
        user_id = self.context.gateway.current_user_id()
        category = Category(
            id=category_id or str(uuid4()),
            user_id=user_id,
            name=name,
            color=color,
            icon=icon,
            description=description,
        )
        return self.context.categories.upsert(category)

    def delete_category(self, category_id: str) -> bool:
        return self.context.categories.delete(category_id)

    def fetch(self, category_id: str) -> Optional[Category]:
        return self.context.categories.fetch(category_id)
