from __future__ import annotations

from http import HTTPStatus
import importlib
import os
import sys
import time
from typing import Any, Dict, Optional

from src.editor_core.contracts import ToolResult

from .vision_tool_helpers import build_media_ref, extract_text_and_usage, infer_media_type, resolve_api_base, resolve_api_key, resolve_model


class VisionTool:
    """Vision entry points backed by DashScope MultiModalConversation."""

    def __init__(self) -> None:
        self._timeout_seconds = int(os.getenv("AICLIP_VISION_TIMEOUT", "180"))
        self._max_retries = max(0, int(os.getenv("AICLIP_VISION_MAX_RETRIES", "3")))
        self._retry_base_seconds = float(os.getenv("AICLIP_VISION_RETRY_BASE", "1.5"))

    def vision_analyze_media(self, media_path: str, prompt: str = "请输出该媒体的关键事件与时间点。", media_type: Optional[str] = None, model: Optional[str] = None, api_base: Optional[str] = None, api_key: Optional[str] = None, fps: float = 2.0, temperature: float = 0.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        resolved_key = resolve_api_key(api_key)
        if not resolved_key:
            return ToolResult(ok=False, status="error", code="vision_analyze_media.missing_api_key", message="AICLIP_VISION_API_KEY or DASHSCOPE_API_KEY is not configured", operation="vision_analyze_media", error="missing_api_key", next_actions=["configure_env"]).to_dict()
        resolved_base = resolve_api_base(api_base)
        resolved_model = resolve_model(model)
        resolved_type = infer_media_type(media_path, media_type)
        media_ref, input_mode = build_media_ref(media_path)
        try:
            dashscope = importlib.import_module("dashscope")
            multi_modal_conversation = getattr(dashscope, "MultiModalConversation")
        except Exception:
            install_cmd = f'"{sys.executable}" -m pip install dashscope'
            return ToolResult(ok=False, status="error", code="vision_analyze_media.missing_dashscope_sdk", message="dashscope SDK is not installed", operation="vision_analyze_media", error="missing_dashscope_sdk", next_actions=["pip_install_dashscope"], state={"python_executable": sys.executable, "install_command": install_cmd}).to_dict()
        setattr(dashscope, "base_http_api_url", resolved_base)
        message_content: list[Dict[str, Any]] = []
        if resolved_type == "video":
            media_item: Dict[str, Any] = {"video": media_ref}
            if fps > 0:
                media_item["fps"] = float(fps)
            message_content.append(media_item)
        else:
            message_content.append({"image": media_ref})
        message_content.append({"text": prompt})
        messages = [{"role": "user", "content": message_content}]
        response_payload: Any = None
        last_error: Optional[str] = None
        retry_count = 0
        for attempt in range(self._max_retries + 1):
            try:
                response = multi_modal_conversation.call(api_key=resolved_key, model=resolved_model, messages=messages, temperature=float(temperature), max_tokens=max_tokens, timeout=self._timeout_seconds)
                response_payload = response
                break
            except Exception as exc:
                last_error = str(exc)
                retry_count = attempt
                if attempt >= self._max_retries:
                    break
                time.sleep(self._retry_base_seconds * (2 ** attempt))
        if response_payload is None:
            return ToolResult(ok=False, status="error", code="vision_analyze_media.request_failed", message=last_error or "Vision request failed", operation="vision_analyze_media", error=last_error, state={"media_path": media_path, "media_type": resolved_type, "model": resolved_model, "api_base": resolved_base, "retry_count": retry_count}).to_dict()
        text, usage, finish_reason, status_code, status_message = extract_text_and_usage(response_payload)
        ok = status_code in (None, HTTPStatus.OK, 200)
        return ToolResult(ok=ok, status="ok" if ok else "error", code="vision_analyze_media.completed" if ok else "vision_analyze_media.http_error", message=text or status_message or "Vision analysis completed", operation="vision_analyze_media", content=text, summary=text or status_message or "Vision analysis completed", state={"media_path": media_path, "media_ref": media_ref, "input_mode": input_mode, "media_type": resolved_type, "model": resolved_model, "api_base": resolved_base, "usage": usage, "finish_reason": finish_reason, "status_code": status_code, "retry_count": retry_count}).to_dict()
