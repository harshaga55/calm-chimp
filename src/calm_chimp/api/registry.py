from __future__ import annotations

import inspect
import types
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Union, get_args, get_origin

JsonSchema = Dict[str, Any]


def _json_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            dict: "object",
            list: "array",
        }
        return mapping.get(annotation, "string")
    if origin in (list, List):
        return "array"
    if origin in (dict, Dict):
        return "object"
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        return _json_type(args[0]) if args else "string"
    return "string"


def _parameter_schema(param: inspect.Parameter) -> JsonSchema:
    schema: JsonSchema = {"type": _json_type(param.annotation)}
    default = param.default
    if default is not inspect._empty and default is not None:
        if isinstance(default, (str, int, float, bool)):
            schema["default"] = default
    return schema


@dataclass(frozen=True)
class ApiFunction:
    name: str
    func: Callable[..., Any]
    description: str
    category: str
    tags: tuple[str, ...]
    signature: inspect.Signature

    @property
    def parameters(self) -> Dict[str, str]:
        return {param.name: str(param.annotation) for param in self.signature.parameters.values()}

    @property
    def parameter_schema(self) -> JsonSchema:
        schema: JsonSchema = {"type": "object", "properties": {}, "required": []}
        for param in self.signature.parameters.values():
            schema["properties"][param.name] = _parameter_schema(param)
            if param.default is inspect._empty:
                schema["required"].append(param.name)
        if not schema["required"]:
            schema.pop("required")
        return schema

    def as_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameter_schema,
            },
        }


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
            signature=inspect.signature(func),
        )
        return func

    return decorator


def get_api_functions() -> List[ApiFunction]:
    return list(REGISTRY.values())


def call_api(name: str, **kwargs: Any) -> Any:
    if name not in REGISTRY:
        raise KeyError(f"API function '{name}' is not registered.")
    return REGISTRY[name].func(**kwargs)
