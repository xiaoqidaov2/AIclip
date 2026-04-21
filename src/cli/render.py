from __future__ import annotations

import sys
import threading
import time
from typing import Any, Optional

from .render_impl import process_stream_message, process_tool_result, render_response, render_stream_simple, show_tool_call
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
        self._spinner_thread: Optional[threading.Thread] = None
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
                    messages = chunk.get("model", {}).get("messages", []) if "model" in chunk else chunk.get("tools", {}).get("messages", []) if "tools" in chunk else chunk.get("agent", {}).get("messages", []) if "agent" in chunk else chunk.get("messages", [])
                    for msg in messages:
                        collected_messages.append(msg)
                        if type(msg).__name__ == "ToolMessage":
                            process_tool_result(self, msg)
                            self.last_tool_results.append(getattr(msg, "content", ""))
                        else:
                            final_content = process_stream_message(self, msg, tool_calls_seen, final_content)
                self.clear_status()
                return final_content, collected_messages
            except Exception as exc:
                self.clear_status()
                error_str = str(exc).lower()
                is_retryable = "429" in error_str or "rate limit" in error_str or "tpm limit" in error_str or ("null value for" in error_str and "choices" in error_str)
                if is_retryable and callable(stream_iterator_provider):
                    consecutive_failures = 0 if made_progress else consecutive_failures
                    consecutive_failures += 1
                    delay = base_delay * (2 ** (consecutive_failures - 1))
                    print(f"\n{self.theme.warn('[rate]')} 429 / rate limit. {delay}s 后重试 (连续失败 {consecutive_failures}/{max_consecutive_failures})", flush=True)
                    time.sleep(delay)
                    continue
                print(f"\n{self.theme.error('[stream]')} {exc}")
                return final_content, collected_messages
        self.clear_status()
        return final_content, collected_messages

    def render_response(self, response: Any) -> str:
        return render_response(self, response)


__all__ = ["CLIRenderer", "render_stream_simple", "show_tool_call"]
