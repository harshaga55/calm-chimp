from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ApiFunction:
    """Metadata describing a deterministic API function."""

    name: str
    func: Callable[..., Any]
    description: str
    category: str
    tags: tuple[str, ...]

    @property
    def parameters(self) -> Dict[str, str]:
        return {param.name: str(param.annotation) for param in signature(self.func).parameters.values()}


API_REGISTRY: Dict[str, ApiFunction] = {}


def register_api(
    name: str,
    *,
    description: str,
    category: str,
    tags: Optional[Iterable[str]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to register deterministic API functions."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        key = name
        if key in API_REGISTRY:
            raise ValueError(f"API function '{key}' already registered.")
        API_REGISTRY[key] = ApiFunction(
            name=key,
            func=func,
            description=description,
            category=category,
            tags=tuple(tags or ()),
        )
        return func

    return decorator


def get_api_functions() -> List[ApiFunction]:
    return list(API_REGISTRY.values())


def call_api(name: str, **kwargs: Any) -> Any:
    if name not in API_REGISTRY:
        raise KeyError(f"API function '{name}' not found.")
    return API_REGISTRY[name].func(**kwargs)
