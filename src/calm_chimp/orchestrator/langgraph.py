from __future__ import annotations

import json
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from ..api import call_api
from .chat import ChatOrchestrator, ChatResult


class GraphState(TypedDict, total=False):
    history: List[Dict[str, str]]
    user_message: str
    chat_result: ChatResult
    tool_output: Dict[str, Any]


class LangGraphOrchestrator:
    def __init__(self) -> None:
        self._chat = ChatOrchestrator()
        self._graph = StateGraph(GraphState)
        self._graph.add_node("chat", self._chat_node)
        self._graph.add_node("tool", self._tool_node)
        self._graph.add_edge("chat", "tool")
        self._graph.add_edge("tool", END)
        self._compiled = self._graph.compile()

    def _chat_node(self, state: GraphState) -> GraphState:
        history = state.get("history", [])
        user_message = state["user_message"]
        result = self._chat.orchestrate(history, user_message)
        new_history = history + [{"role": "user", "content": user_message}]
        if result.has_tool_call:
            new_history.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "tool": result.tool_name,
                            "arguments": result.arguments,
                            "assistant_message": " ".join(result.messages),
                        }
                    ),
                }
            )
        else:
            for message in result.messages:
                new_history.append({"role": "assistant", "content": message})
        return {
            "history": new_history,
            "user_message": user_message,
            "chat_result": result,
        }

    def _tool_node(self, state: GraphState) -> GraphState:
        result = state.get("chat_result")
        if not result or not result.has_tool_call:
            return state
        output = call_api(result.tool_name, **result.arguments)
        history = state.get("history", [])
        history.append({"role": "assistant", "content": json.dumps(output)})
        return {
            "history": history,
            "user_message": state["user_message"],
            "chat_result": result,
            "tool_output": output,
        }

    def invoke(self, history: List[Dict[str, str]], user_message: str) -> Dict[str, Any]:
        initial_state: GraphState = {
            "history": history,
            "user_message": user_message,
        }
        final_state = self._compiled.invoke(initial_state)
        chat_result = final_state.get("chat_result")
        tool_output = final_state.get("tool_output")
        response = {
            "messages": chat_result.messages if chat_result else [],
            "tool_name": chat_result.tool_name if chat_result else None,
            "arguments": chat_result.arguments if chat_result else {},
            "tool_output": tool_output,
        }
        return response
