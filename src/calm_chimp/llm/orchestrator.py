from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from openai import AzureOpenAI

from ..api import get_api_functions
from ..settings import get_settings


_SYSTEM_PROMPT_TEMPLATE = (
    "You are the Calm Chimp assistant. Always respond with a JSON object. "
    "If the user request maps to one of the provided tools, respond with:\n"
    '{{"type": "tool", "tool_name": "...", "arguments": {{}}, "assistant_message": "..."}}.\n'
    "Otherwise respond with:\n"
    '{{"type": "message", "assistant_message": "..."}}.\n'
    "Available deterministic tools (name, description, parameters):\n{tool_catalog}\n"
    "Only call tools you are confident match the request. Prefer calling a tool once with best-effort values instead of asking the user "
    "for more details. When information is missing, choose sensible defaults (use the default calendar, assume a 60 minute duration, "
    "pick the next reasonable date/time) and mention any assumptions in `assistant_message`. Keep arguments minimal and well-typed."
)


@dataclass
class ChatOrchestrationResult:
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
        self._tool_names = {func.name for func in self._tool_specs}
        tool_catalog = [
            {
                "name": func.name,
                "description": func.description,
                "parameters": func.parameters,
            }
            for func in self._tool_specs
        ]
        self._system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(tool_catalog=json.dumps(tool_catalog, indent=2))

    def _ensure_client(self) -> Optional[AzureOpenAI]:
        if not self.settings.azure_openai.is_configured:
            return None
        if self._client is None:
            azure = self.settings.azure_openai
            self._client = AzureOpenAI(
                api_key=azure.api_key,
                api_version=azure.api_version,
                azure_endpoint=azure.endpoint,
            )
        return self._client

    def orchestrate(self, history: List[Dict[str, str]], user_message: str) -> ChatOrchestrationResult:
        if not self.settings.azure_openai.is_configured:
            missing = ", ".join(self.settings.azure_openai.missing_env_vars)
            info = (
                "Azure OpenAI is not configured. "
                f"Set these environment variables to enable tool-aware chat: {missing or 'unknown'}."
            )
            fallback = self._keyword_fallback(user_message)
            fallback.messages.insert(0, info)
            return fallback

        client = self._ensure_client()
        if client is None:
            return self._keyword_fallback(user_message)

        messages = history + [{"role": "user", "content": user_message}]
        try:
            completion = client.chat.completions.create(
                model=self.settings.azure_openai.deployment,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    *messages,
                ],
            )
        except Exception as exc:  # noqa: BLE001
            fallback = self._keyword_fallback(user_message)
            fallback.messages.insert(0, f"Azure OpenAI request failed: {exc}")
            return fallback

        choice = completion.choices[0].message.content or ""
        return self._parse_choice(choice)

    def _parse_choice(self, content: str) -> ChatOrchestrationResult:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return ChatOrchestrationResult(messages=[content])

        message = payload.get("assistant_message") or payload.get("message") or ""
        if payload.get("type") == "tool":
            tool_name = payload.get("tool_name")
            if tool_name in self._tool_names:
                arguments = payload.get("arguments") or {}
                if not isinstance(arguments, dict):
                    arguments = {}
                if not message:
                    message = f"I'll use `{tool_name}` to handle that."
                return ChatOrchestrationResult(
                    messages=[message] if message else [],
                    tool_name=tool_name,
                    arguments=arguments,
                    raw=payload,
                )
        return ChatOrchestrationResult(messages=[message] if message else [], raw=payload)

    def _keyword_fallback(self, user_message: str) -> ChatOrchestrationResult:
        lowered = user_message.lower()
        mapping = self._keyword_mappings()
        for keywords, tool_name in mapping:
            if all(keyword in lowered for keyword in keywords):
                return ChatOrchestrationResult(
                    messages=[
                        "Routing request using offline heuristics."
                    ],
                    tool_name=tool_name,
                    arguments={},
                )
        return ChatOrchestrationResult(messages=["I could not understand the request. Try rephrasing or use /help."])

    def _keyword_mappings(self) -> Iterable[tuple[tuple[str, ...], str]]:
        return (
            (("pending",), "list_pending_tasks_ordered_by_due_date"),
            (("overdue",), "list_overdue_tasks"),
            (("today", "tasks"), "list_tasks_due_today"),
            (("tomorrow",), "list_tasks_due_tomorrow"),
            (("history",), "list_recent_history_actions"),
        )
