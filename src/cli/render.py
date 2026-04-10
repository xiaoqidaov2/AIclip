from typing import Any, Dict, Iterator
import sys
import json
import threading
import time

from langchain_core.messages import AIMessage, ToolMessage


class CLIRenderer:
    """Render agent responses with animated loading status, structured sections, and smart truncation."""

    MAX_SUMMARY_LENGTH = 200
    # Use ASCII-compatible spinner for Windows
    SPINNER_CHARS = ["|", "/", "-", "\\"]

    def __init__(self):
        self.verbose = False
        self._spinner_idx = 0
        self._current_status = ""
        self._has_status = False
        self._spinner_running = False
        self._spinner_thread = None
        self._lock = threading.Lock()
        self.last_tool_calls = []
        self.last_tool_results = []

    def set_verbose(self, enabled: bool) -> None:
        self.verbose = enabled

    def show_status(self, text: str) -> None:
        """Show an animated transient status line."""
        with self._lock:
            self._current_status = text
            self._has_status = True

            if self._spinner_running:
                return

            self._spinner_running = True
            self._spinner_thread = threading.Thread(target=self._spin, daemon=True)
            self._spinner_thread.start()

    def clear_status(self) -> None:
        """Clear the current status line and stop spinner."""
        with self._lock:
            self._spinner_running = False
            self._has_status = False
            status_length = len(self._current_status)
            self._current_status = ""

        sys.stdout.write("\r" + " " * (status_length + 10) + "\r")
        sys.stdout.flush()

    def _spin(self) -> None:
        """Run spinner animation in background thread."""
        while True:
            with self._lock:
                if not self._spinner_running:
                    break
                text = self._current_status
                spinner = self.SPINNER_CHARS[self._spinner_idx % len(self.SPINNER_CHARS)]
                self._spinner_idx += 1

            sys.stdout.write(f"\r{spinner} {text}")
            sys.stdout.flush()
            time.sleep(0.15)

    def render_stream(self, stream_iterator: Iterator) -> tuple[str, list[Any]]:
        """Render agent output from a stream, showing status and structured sections."""
        final_content = ""
        collected_messages = []
        tool_calls_seen = set()
        self.last_tool_calls = []
        self.last_tool_results = []

        try:
            for chunk in stream_iterator:
                if not isinstance(chunk, dict):
                    continue

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

        except Exception as e:
            self.clear_status()
            print(f"\n流式处理出错: {e}")

        self.clear_status()
        return final_content, collected_messages

    def _process_stream_message(self, msg: Any, tool_calls_seen: set, current_content: str) -> str:
        msg_type = type(msg).__name__

        if msg_type == "AIMessage":
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
            if content and isinstance(content, str) and content.strip():
                current_content = content

        return current_content

    def _process_tool_result(self, msg: Any) -> None:
        name = getattr(msg, "name", "tool")
        content = getattr(msg, "content", "")
        summary = self._extract_summary(content)

        self.clear_status()
        if self.verbose:
            print(f"\n└─ [{name}] 完成")
            if len(str(content)) > self.MAX_SUMMARY_LENGTH:
                print(f"   结果: {summary}")
                print("   (完整内容已截断，使用 /verbose 查看)")
            else:
                print(f"   结果: {content}")
        else:
            print(f"\n└─ [{name}] {summary}")

    def _show_tool_call(self, name: str, args: Dict) -> None:
        self.clear_status()
        print(f"\n┌─ 调用工具: {name}")
        if args:
            args_str = self._format_args(args)
            print(f"│  参数: {args_str}")
        self.show_status(f"正在执行 {name}...")
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
        self.show_status("思考中...")

        messages = response.get("messages", []) if isinstance(response, dict) else []
        if not messages:
            self.clear_status()
            print("没有响应消息")
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
            print(f"\n{final_content}")

        return final_content

    def _extract_summary(self, content: str) -> str:
        if not content:
            return "完成"

        text = str(content)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                if "summary" in data:
                    return data["summary"]
                if "ok" in data:
                    return "成功" if data["ok"] else "失败"
                if "segment_count" in data and "format" in data:
                    summary = f"已生成 {data['segment_count']} 段 {str(data['format']).upper()} 字幕"
                    if "output_path" in data:
                        summary += f"，已保存到 {data['output_path']}"
                    return summary
                if "text" in data and "language" in data:
                    return f"已转录文本，语言: {data['language']}"
        except (json.JSONDecodeError, TypeError):
            pass

        if len(text) <= self.MAX_SUMMARY_LENGTH:
            return text
        return text[:self.MAX_SUMMARY_LENGTH - 3] + "..."


def render_stream_simple(stream_iterator: Iterator, verbose: bool = False) -> str:
    renderer = CLIRenderer()
    renderer.set_verbose(verbose)
    return renderer.render_stream(stream_iterator)
