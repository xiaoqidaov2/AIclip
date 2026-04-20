from __future__ import annotations

import json
import sys
import threading
import time
from typing import Any, Dict

from langchain_core.messages import AIMessage, ToolMessage

from .theme import CliTheme


class CLIRenderer:
    """Render agent responses with a spinner and compact structured summaries."""

    MAX_SUMMARY_LENGTH = 200
    SPINNER_CHARS = ["|", "/", "-", "\\"]
    STATIC_PROGRESS_TOOLS = {"render_project"}

    def __init__(self) -> None:
        self.verbose = False
        self.theme = CliTheme()
        self._spinner_idx = 0
        self._current_status = ""
        self._has_status = False
        self._spinner_running = False
        self._spinner_thread = None
        self._lock = threading.Lock()
        self.last_tool_calls: list[dict[str, Any]] = []
        self.last_tool_results: list[Any] = []

    def set_verbose(self, enabled: bool) -> None:
        self.verbose = enabled

    def show_status(self, text: str) -> None:
        with self._lock:
            self._current_status = text
            self._has_status = True
            if self._spinner_running:
                return

            self._spinner_running = True
            self._spinner_thread = threading.Thread(target=self._spin, daemon=True)
            self._spinner_thread.start()

    def clear_status(self) -> None:
        with self._lock:
            self._spinner_running = False
            self._has_status = False
            status_length = len(self._current_status)
            self._current_status = ""

        sys.stdout.write("\r" + " " * (status_length + 10) + "\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        while True:
            with self._lock:
                if not self._spinner_running:
                    break
                text = self._current_status
                spinner = self.SPINNER_CHARS[self._spinner_idx % len(self.SPINNER_CHARS)]
                self._spinner_idx += 1

            sys.stdout.write(f"\r{self.theme.muted(spinner)} {self.theme.info(text)}")
            sys.stdout.flush()
            time.sleep(0.15)

    def render_stream(self, stream_iterator_provider: Any) -> tuple[str, list[Any]]:
        max_consecutive_failures = 5
        base_delay = 2

        consecutive_failures = 0
        final_content = ""
        collected_messages: list[Any] = []
        tool_calls_seen: set[str] = set()

        while consecutive_failures < max_consecutive_failures:
            self.last_tool_calls = []
            self.last_tool_results = []
            made_progress = False

            stream_iterator = stream_iterator_provider() if callable(stream_iterator_provider) else stream_iterator_provider

            try:
                for chunk in stream_iterator:
                    if not isinstance(chunk, dict):
                        continue

                    made_progress = True
                    messages = []
                    if "model" in chunk:
                        messages = chunk["model"].get("messages", [])
                    elif "tools" in chunk:
                        messages = chunk["tools"].get("messages", [])
                    elif "agent" in chunk:
                        messages = chunk["agent"].get("messages", [])
                    elif "messages" in chunk:
                        messages = chunk["messages"]

                    for msg in messages:
                        collected_messages.append(msg)
                        msg_type = type(msg).__name__
                        if msg_type == "ToolMessage":
                            self._process_tool_result(msg)
                            self.last_tool_results.append(getattr(msg, "content", ""))
                        else:
                            final_content = self._process_stream_message(msg, tool_calls_seen, final_content)
                self.clear_status()
                return final_content, collected_messages

            except Exception as e:
                self.clear_status()
                error_str = str(e).lower()
                is_retryable = (
                    "429" in error_str
                    or "rate limit" in error_str
                    or "tpm limit" in error_str
                    or ("null value for" in error_str and "choices" in error_str)
                )

                if is_retryable and callable(stream_iterator_provider):
                    if made_progress:
                        consecutive_failures = 0
                    consecutive_failures += 1
                    delay = base_delay * (2 ** (consecutive_failures - 1))
                    print(
                        f"\n{self.theme.warn('[rate]')} 429 / rate limit. {delay}s 后重试 "
                        f"(连续失败 {consecutive_failures}/{max_consecutive_failures})",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                else:
                    print(f"\n{self.theme.error('[stream]')} {e}")
                    return final_content, collected_messages

        self.clear_status()
        return final_content, collected_messages

    def _process_stream_message(self, msg: Any, tool_calls_seen: set, current_content: str) -> str:
        if type(msg).__name__ == "AIMessage":
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id not in tool_calls_seen:
                        tool_calls_seen.add(tc_id)
                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})
                        self._show_tool_call(name, args)

            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                current_content = content
        return current_content

    def _process_tool_result(self, msg: Any) -> None:
        name = getattr(msg, "name", "tool")
        content = getattr(msg, "content", "")
        summary = self._extract_summary(content)
        extracted_content = self._extract_content(content)

        self.clear_status()
        if self.verbose:
            print(f"\n{self.theme.success('└─')} {self.theme.label(f'[{name}]')} 完成")
            if len(str(content)) > self.MAX_SUMMARY_LENGTH:
                print(f"   {self.theme.muted('结果:')} {summary}")
                print(f"   {self.theme.muted('(完整内容已截断，使用 /verbose 查看)')}")
            else:
                print(f"   {self.theme.muted('结果:')} {content}")
        else:
            print(f"\n{self.theme.success('└─')} {self.theme.label(f'[{name}]')} {summary}")

        if extracted_content and extracted_content != summary:
            print(f"   {self.theme.muted('Content:')} {self._truncate_text(extracted_content, self.MAX_SUMMARY_LENGTH)}")

    def _show_tool_call(self, name: str, args: Dict) -> None:
        self.clear_status()
        print(f"\n{self.theme.info('├─')} 调用工具: {self.theme.accent(name)}")
        if args:
            args_str = self._format_args(args)
            print(f"{self.theme.info('│  ')} 参数: {self.theme.muted(args_str)}")
        if name in self.STATIC_PROGRESS_TOOLS:
            print(self.theme.info(f"[tool] {name} running; MoviePy progress bar follows below."))
        else:
            self.show_status(f"Executing {name}...")
        self.last_tool_calls.append({"name": name, "args": args})

    def _format_args(self, args: Dict) -> str:
        parts = []
        for k, v in args.items():
            v_str = str(v)
            if len(v_str) > 60:
                v_str = v_str[:57] + "..."
            parts.append(f"{k}={repr(v_str) if ' ' in v_str else v_str}")
        return ", ".join(parts)

    def render_response(self, response: Any) -> str:
        self.show_status("Thinking...")

        messages = response.get("messages", []) if isinstance(response, dict) else []
        if not messages:
            self.clear_status()
            print(self.theme.warn("没有响应消息"))
            return ""

        final_content = ""
        for msg in messages:
            msg_type = type(msg).__name__
            if msg_type == "AIMessage":
                tool_calls = getattr(msg, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})
                        self._show_tool_call(name, args)

                content = getattr(msg, "content", "")
                if content:
                    final_content = content
            elif msg_type == "ToolMessage":
                self._process_tool_result(msg)

        self.clear_status()

        if final_content:
            print(f"\n{self.theme.title(final_content)}")

        return final_content

    def _extract_summary(self, content: str) -> str:
        if not content:
            return "完成"

        text = str(content)
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                decision = data.get("decision")
                if isinstance(decision, dict):
                    parts = []
                    for key in ("operation", "code", "status"):
                        value = decision.get(key)
                        if value not in (None, ""):
                            parts.append(str(value))
                    state = decision.get("state")
                    if isinstance(state, dict):
                        for key in ("project_path", "output_path", "media_path", "final_path"):
                            value = state.get(key)
                            if value not in (None, ""):
                                parts.append(f"{key}={value}")
                                break
                    next_actions = decision.get("next_actions") or []
                    if next_actions:
                        parts.append(f"next={','.join(map(str, next_actions[:3]))}")
                    if parts:
                        return " | ".join(parts)

                if "operation" in data and "status" in data:
                    return f"{data['operation']} | {data['status']}"
                if "code" in data:
                    return str(data["code"])
                if "status" in data:
                    return str(data["status"])
                if "ok" in data:
                    return "成功" if data["ok"] else "失败"

                for key in ("project_path", "output_path", "media_path", "subtitle_path"):
                    if key in data and data[key]:
                        return f"{data.get('operation', 'tool')} | {key}={data[key]}"
        except (json.JSONDecodeError, TypeError):
            pass

        if len(text) <= self.MAX_SUMMARY_LENGTH:
            return text
        return text[: self.MAX_SUMMARY_LENGTH - 3] + "..."

    def _extract_content(self, content: Any) -> str:
        if isinstance(content, dict):
            value = content.get("content")
            if value is None:
                value = content.get("summary")
            if value is None:
                value = content.get("message")
            return str(value).strip() if value is not None else ""

        if content is None:
            return ""

        if isinstance(content, str):
            text = content.strip()
            if not text:
                return ""
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    value = data.get("content") or data.get("summary") or data.get("message")
                    if value is not None:
                        return str(value).strip()
            except (json.JSONDecodeError, TypeError):
                pass
            return text

        return str(content).strip()

    def _truncate_text(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


def render_stream_simple(stream_iterator_provider: Any, verbose: bool = False) -> str:
    renderer = CLIRenderer()
    renderer.set_verbose(verbose)
    return renderer.render_stream(stream_iterator_provider)[0]
