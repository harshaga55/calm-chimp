from __future__ import annotations

from dataclasses import dataclass, field

from ..services import AuthService, CalendarService, CategoryService, ServiceContext


@dataclass(slots=True)
class ApiState:
    context: ServiceContext = field(default_factory=ServiceContext)
    auth: AuthService = field(init=False)
    calendar: CalendarService = field(init=False)
    categories: CategoryService = field(init=False)

    def __post_init__(self) -> None:
        self.auth = AuthService(self.context)
        self.calendar = CalendarService(self.context)
        self.categories = CategoryService(self.context)


api_state = ApiState()
