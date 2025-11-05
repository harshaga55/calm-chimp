from __future__ import annotations

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from openai import AzureOpenAI

from ..api import get_api_functions
from ..config import get_settings
from .prompts import SYSTEM_PROMPT_TEMPLATE


@dataclass
class ChatResult:
    messages: List[str] = field(default_factory=list)
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None

    @property
    def has_tool_call(self) -> bool:
        return self.tool_name is not None


class ChatOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Optional[AzureOpenAI] = None
        self._tool_specs = sorted(get_api_functions(), key=lambda func: func.name)
        tool_catalog = [
            {
                "name": func.name,
                "description": func.description,
                "parameters": func.parameters,
                "category": func.category,
                "tags": list(func.tags),
            }
            for func in self._tool_specs
        ]
        self._system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_catalog=json.dumps(tool_catalog, indent=2))

    def _ensure_client(self) -> Optional[AzureOpenAI]:
        if not self.settings.azure.is_configured:
            return None
        if self._client is None:
            azure = self.settings.azure
            self._client = AzureOpenAI(
                api_key=azure.api_key,
                api_version=azure.api_version,
                azure_endpoint=azure.endpoint,
            )
        return self._client

    def orchestrate(self, history: List[Dict[str, str]], user_message: str) -> ChatResult:
        if not self.settings.azure.is_configured:
            fallback = self._keyword_router(user_message)
            missing = ", ".join(self.settings.azure.missing_env_vars)
            fallback.messages.insert(0, f"Azure OpenAI is not configured. Missing: {missing}")
            return fallback

        client = self._ensure_client()
        if client is None:
            return self._keyword_router(user_message)

        messages = history + [{"role": "user", "content": user_message}]
        try:
            completion = client.chat.completions.create(
                model=self.settings.azure.deployment,
                temperature=0.2,
                messages=[{"role": "system", "content": self._system_prompt}, *messages],
            )
        except Exception as exc:  # noqa: BLE001
            fallback = self._keyword_router(user_message)
            fallback.messages.insert(0, f"Azure request failed: {exc}")
            return fallback

        content = completion.choices[0].message.content or ""
        return self._parse_choice(content)

    def _parse_choice(self, content: str) -> ChatResult:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return ChatResult(messages=[content])

        message = payload.get("assistant_message") or payload.get("message") or ""
        if payload.get("type") == "tool":
            tool_name = payload.get("tool_name")
            if tool_name and tool_name in {spec.name for spec in self._tool_specs}:
                arguments = payload.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                return ChatResult(
                    messages=[message] if message else [],
                    tool_name=tool_name,
                    arguments=arguments,
                    raw=payload,
                )
        return ChatResult(messages=[message] if message else [], raw=payload)

    # ------------------------------------------------------------------ fallback

    def _keyword_router(self, user_message: str) -> ChatResult:
        lowered = user_message.lower()
        for keywords, tool_name, arguments in self._keyword_mappings():
            if all(keyword in lowered for keyword in keywords):
                return ChatResult(
                    messages=[f"Routing with offline heuristic using `{tool_name}`."],
                    tool_name=tool_name,
                    arguments=arguments,
                )
        return ChatResult(messages=["I could not map that request to a known tool. Try asking differently or use /help."])

    def _keyword_mappings(self) -> Iterable[tuple[tuple[str, ...], str, Dict[str, Any]]]:
        today_iso = datetime.utcnow().date().isoformat()
        return (
            (("today", "events"), "events_for_day", {"day": today_iso}),
            (("tomorrow", "events"), "events_for_day", {"day": self._offset_day(1)}),
            (("list", "categories"), "list_categories", {}),
            (("refresh", "timeline"), "refresh_timeline", {}),
        )

    def _offset_day(self, offset: int) -> str:
        from datetime import datetime, timedelta

        return (datetime.utcnow().date() + timedelta(days=offset)).isoformat()
