from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Set


class CoordinatorStreamMixin:
    async def _run_agent_with_visibility(
        self, agent: Any, messages: List[Dict[str, Any]], label: str
    ) -> Any:
        if hasattr(agent, "stream"):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._drain_stream_sync, agent, messages, label)
        if hasattr(agent, "ainvoke"):
            return await agent.ainvoke({"messages": messages})
        if hasattr(agent, "invoke"):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, agent.invoke, {"messages": messages})
        return {"result": f"执行: {messages[-1].get('content', '')}"}

    def _drain_stream_sync(self, agent: Any, messages: List[Dict[str, Any]], label: str) -> Any:
        max_consecutive_failures = 5
        base_delay = 2
        consecutive_failures = 0
        final_content = ""
        collected_messages: List[Any] = []
        seen_tool_calls: Set[str] = set()
        while consecutive_failures < max_consecutive_failures:
            made_progress = False
            try:
                for chunk in agent.stream({"messages": messages}):
                    if not isinstance(chunk, dict):
                        continue
                    made_progress = True
                    chunk_messages = self._chunk_messages(chunk)
                    for msg in chunk_messages:
                        collected_messages.append(msg)
                        msg_type = type(msg).__name__
                        if msg_type == "ToolMessage" or (hasattr(msg, "name") and not getattr(msg, "tool_calls", None)):
                            self._print_tool_result(msg, label)
                        elif msg_type in {"AIMessage", "AIMessageChunk"} or hasattr(msg, "tool_calls") or hasattr(msg, "content"):
                            final_content = self._print_ai_message(msg, seen_tool_calls, final_content, label)
                return {"messages": collected_messages, "content": final_content}
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = "429" in error_str or "rate limit" in error_str or "tpm limit" in error_str or ("null value for" in error_str and "choices" in error_str)
                if not is_retryable:
                    print(f"\n└─ [{label}] 流式执行失败: {e}", flush=True)
                    return {"messages": collected_messages, "content": final_content}
                consecutive_failures = 1 if made_progress else consecutive_failures + 1
                delay = base_delay * (2 ** (consecutive_failures - 1))
                print(f"\n[!] 触发频率限制或请求拥挤 (Rate Limit, 429). {delay} 秒后尝试重新连接 (连续失败 {consecutive_failures}/{max_consecutive_failures} 次)...", flush=True)
                time.sleep(delay)
        return {"messages": collected_messages, "content": final_content}

    def _chunk_messages(self, chunk: Dict[str, Any]) -> List[Any]:
        if "model" in chunk:
            return chunk["model"].get("messages", [])
        if "tools" in chunk:
            return chunk["tools"].get("messages", [])
        if "agent" in chunk:
            return chunk["agent"].get("messages", [])
        return chunk.get("messages", [])

    def _print_ai_message(self, msg: Any, seen_tool_calls: Set[str], current_content: str, label: str) -> str:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id", "")
                if tool_call_id and tool_call_id in seen_tool_calls:
                    continue
                if tool_call_id:
                    seen_tool_calls.add(tool_call_id)
                print(f"\n┌─ [{label}] 调用工具: {tool_call.get('name', 'unknown')}", flush=True)
                args = tool_call.get("args", {})
                if args:
                    print(f"│  参数: {self._format_args(args)}", flush=True)
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.strip() and content != current_content:
            current_content = content
            print(f"\n└─ [{label}] AI: {self._truncate_text(content, 500)}", flush=True)
        return current_content

    def _print_tool_result(self, msg: Any, label: str) -> None:
        print(f"\n└─ [{label}] 工具结果: [{getattr(msg, 'name', 'tool')}] {self._truncate_text(str(getattr(msg, 'content', '')), 500)}", flush=True)

    def _format_args(self, args: Dict[str, Any]) -> str:
        if not args:
            return ""
        parts = []
        for key, value in args.items():
            value_text = str(value)
            if len(value_text) > 60:
                value_text = value_text[:57] + "..."
            parts.append(f"{key}={value_text}")
        return "(" + ", ".join(parts) + ")"

    def _truncate_text(self, text: str, limit: int) -> str:
        return text if len(text) <= limit else text[: limit - 3] + "..."