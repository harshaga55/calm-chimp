from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ApiFunction:
    name: str
    func: Callable[..., Any]
    description: str
    category: str
    tags: tuple[str, ...]

    @property
    def parameters(self) -> Dict[str, str]:
        return {param.name: str(param.annotation) for param in inspect.signature(self.func).parameters.values()}


REGISTRY: Dict[str, ApiFunction] = {}


def register_api(
    name: str,
    *,
    description: str,
    category: str,
    tags: Optional[Iterable[str]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in REGISTRY:
            raise ValueError(f"API function '{name}' is already registered.")
        REGISTRY[name] = ApiFunction(
            name=name,
            func=func,
            description=description,
            category=category,
            tags=tuple(tags or ()),
        )
        return func

    return decorator


def get_api_functions() -> List[ApiFunction]:
    return list(REGISTRY.values())


def call_api(name: str, **kwargs: Any) -> Any:
    if name not in REGISTRY:
        raise KeyError(f"API function '{name}' is not registered.")
    return REGISTRY[name].func(**kwargs)
