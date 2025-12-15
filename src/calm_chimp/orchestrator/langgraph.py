from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..api import call_api, get_api_functions
from ..config import get_settings
from .prompts import SYSTEM_PROMPT
from .verifiers import VerificationResult, verify_tool_output


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class LangGraphOrchestrator:
    """Thin, single-step orchestrator that lets the model pick one tool."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = self._build_client()
        self._tool_specs = get_api_functions()
        self._tools = [spec.as_tool() for spec in self._tool_specs]

    # ------------------------------------------------------------------ public API

    def invoke(self, history: List[Dict[str, str]], user_message: str) -> Dict[str, Any]:
        history = history or []
        if not self._client:
            return self._offline_route(user_message, reason="LLM not configured")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_message}]
        try:
            completion = self._client.chat.completions.create(
                model=self.settings.llm.model,
                temperature=0.2,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
            )
        except Exception as exc:  # noqa: BLE001
            return self._offline_route(user_message, reason=str(exc))

        message = completion.choices[0].message
        response_messages: List[str] = []
        tool_name: Optional[str] = None
        arguments: Dict[str, Any] = {}
        tool_output: Optional[Dict[str, Any]] = None
        verification: Optional[VerificationResult] = None

        if message.tool_calls:
            call = message.tool_calls[0]
            tool_name = call.function.name
            arguments = self._safe_json(call.function.arguments)
            try:
                tool_output = call_api(tool_name, **arguments)
                verification = verify_tool_output(tool_name, tool_output)
                response_messages.append(self._summarize_tool(tool_name, verification))
            except Exception as exc:  # noqa: BLE001
                response_messages.append(f"Tool `{tool_name}` failed: {exc}")
        else:
            if message.content:
                response_messages.append(message.content.strip())

        self._log_run(
            history=history,
            user_message=user_message,
            tool_name=tool_name,
            arguments=arguments,
            tool_output=tool_output,
            verification=verification,
            model=self.settings.llm.model,
        )
        return {
            "messages": response_messages,
            "tool_name": tool_name,
            "arguments": arguments,
            "tool_output": tool_output,
        }

    # ------------------------------------------------------------------ helpers

    def _build_client(self) -> Optional[OpenAI]:
        if not self.settings.llm.is_configured:
            return None
        default_query = {}
        if self.settings.llm.api_version:
            default_query["api-version"] = self.settings.llm.api_version
        return OpenAI(
            api_key=self.settings.llm.api_key,
            base_url=self.settings.llm.base_url,
            organization=self.settings.llm.organization,
            project=self.settings.llm.project,
            default_query=default_query or None,
        )

    def _safe_json(self, raw: Any) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _offline_route(self, user_message: str, *, reason: str) -> Dict[str, Any]:
        hint = reason or "No model configured."
        normalized = user_message.lower()
        if "today" in normalized and "event" in normalized:
            output: Optional[Dict[str, Any]] = None
            try:
                output = call_api("events_for_day", day=datetime.utcnow().date().isoformat())
            except Exception:
                output = None
            return {
                "messages": [f"{hint} Routing offline to `events_for_day` for today."],
                "tool_name": "events_for_day",
                "arguments": {"day": datetime.utcnow().date().isoformat()},
                "tool_output": output,
            }
        return {
            "messages": [f"{hint} I can still help if you ask for a specific tool call (e.g., list categories)."],
            "tool_name": None,
            "arguments": {},
            "tool_output": None,
        }

    def _summarize_tool(self, tool_name: str, verification: Optional[VerificationResult]) -> str:
        if not verification:
            return f"Ran `{tool_name}`."
        status = "✅" if verification.ok else "⚠️"
        detail = verification.summary or ""
        return f"{status} {tool_name}: {detail}"

    def _log_run(
        self,
        *,
        history: List[Dict[str, str]],
        user_message: str,
        tool_name: Optional[str],
        arguments: Dict[str, Any],
        tool_output: Optional[Dict[str, Any]],
        verification: Optional[VerificationResult],
        model: str,
    ) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "user_message": user_message,
            "history_length": len(history),
            "tool_name": tool_name,
            "arguments": arguments,
            "tool_output": tool_output,
            "verification": verification.to_dict() if verification else None,
        }
        try:
            logs_dir = Path("logs/agent_runs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            filename = logs_dir / f"{datetime.utcnow().isoformat().replace(':', '-')}.json"
            filename.write_text(json.dumps(entry, indent=2, default=_json_default))
        except Exception:
            # Logging failures should never disrupt the UI.
            return
