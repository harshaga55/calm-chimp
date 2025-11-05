from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from hypercorn.asyncio import serve
from hypercorn.config import Config

from ..api import call_api, get_api_functions

app = FastAPI(title="Calm Chimp API", version="1.0.0")


@app.get("/api/functions")
def list_functions() -> Dict[str, Any]:
    functions = []
    for spec in get_api_functions():
        functions.append(
            {
                "name": spec.name,
                "description": spec.description,
                "category": spec.category,
                "tags": list(spec.tags),
                "parameters": spec.parameters,
            }
        )
    return {"functions": functions}


@app.post("/api/functions/{name}")
def invoke_function(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise HTTPException(status_code=400, detail="arguments must be an object")
    try:
        result = call_api(name, **arguments)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"result": result}


async def _serve(config: Config) -> None:
    await serve(app, config)


def run_local_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    config = Config()
    config.bind = [f"{host}:{port}"]
    asyncio.run(_serve(config))
