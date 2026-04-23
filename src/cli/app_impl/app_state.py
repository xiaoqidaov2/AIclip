from __future__ import annotations

import ast
import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, ToolMessage


class CLIAppStateMixin:
    session_state: Any
    theme: Any

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _sync_session_state(self, messages: List[Any]) -> None:
        pending_tool_calls: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, AIMessage):
                tool_calls = getattr(msg, "tool_calls", None) or []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        pending_tool_calls.append(tool_call)
                continue
            if not isinstance(msg, ToolMessage):
                continue
            call = pending_tool_calls.pop(0) if pending_tool_calls else {}
            tool_name = getattr(msg, "name", None) or call.get("name", "tool")
            tool_args = call.get("args") if isinstance(call, dict) else None
            result = self._parse_tool_result(getattr(msg, "content", ""))
            self.session_state.update_from_tool(tool_name, result, tool_args)
            allowed_tools: List[str] = []
            if self.session_state.last_route_decision:
                allowed_tools = self.session_state.last_route_decision.get("allowed_tools", []) or []
            self.session_state.add_stage_audit(
                {
                    "skill": self.session_state.active_skill,
                    "tool": tool_name,
                    "allowed_tools": allowed_tools,
                    "allowed": not allowed_tools or tool_name in allowed_tools,
                }
            )
            if allowed_tools and tool_name not in allowed_tools:
                allowed_text = ", ".join(allowed_tools)
                print(
                    self.theme.warn(
                        f"[audit] blocked-or-offlist tool={tool_name} skill={self.session_state.active_skill} allowed={allowed_text}"
                    )
                )

    def _parse_tool_result(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, dict):
            return content
        if content is None:
            return {}
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {"content": parsed}
            except (json.JSONDecodeError, TypeError):
                try:
                    parsed = ast.literal_eval(text)
                    return parsed if isinstance(parsed, dict) else {"content": parsed}
                except (ValueError, SyntaxError):
                    return {"content": text}
        return {"content": content}

    def _print_session_state(self) -> None:
        print("\nSession state:")
        print(self.session_state.to_context_prompt())