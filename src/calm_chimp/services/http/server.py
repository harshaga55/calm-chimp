from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ...api import ApiFunction, call_api, get_api_functions
from ...logging import configure_logging


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Calm Chimp Local API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ApiCallRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


def _serialize_api_function(api_function: ApiFunction) -> dict:
    return {
        "name": api_function.name,
        "description": api_function.description,
        "category": api_function.category,
        "tags": list(api_function.tags),
        "parameters": api_function.parameters,
    }


@app.get("/api/functions")
async def list_api_functions() -> JSONResponse:
    functions = [_serialize_api_function(func) for func in get_api_functions()]
    return JSONResponse({"functions": functions})


@app.post("/api/functions/{function_name}")
async def invoke_api_function(function_name: str, request: ApiCallRequest) -> JSONResponse:
    try:
        result = call_api(function_name, **request.arguments)
    except KeyError as exc:
        logger.warning("API function not found: %s", function_name)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("API function %s failed", function_name)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logger.debug("API function %s executed successfully", function_name)
    return JSONResponse({"name": function_name, "result": result})


def run_local_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    import asyncio
    from hypercorn.asyncio import serve
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"{host}:{port}"]
    asyncio.run(serve(app, config))
