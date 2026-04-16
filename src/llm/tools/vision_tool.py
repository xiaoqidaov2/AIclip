from __future__ import annotations

from http import HTTPStatus
import importlib
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.editor_core.contracts import ToolResult


class VisionTool:
    """Vision entry points backed by DashScope MultiModalConversation."""

    def __init__(self) -> None:
        self._timeout_seconds = int(os.getenv("AICLIP_VISION_TIMEOUT", "180"))
        self._max_retries = max(0, int(os.getenv("AICLIP_VISION_MAX_RETRIES", "3")))
        self._retry_base_seconds = float(os.getenv("AICLIP_VISION_RETRY_BASE", "1.5"))

    def _resolve_api_base(self, api_base: Optional[str]) -> str:
        value = api_base or os.getenv("AICLIP_VISION_API_BASE") or os.getenv("AICLIP_DASHSCOPE_BASE")
        return (value or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")

    def _resolve_api_key(self, api_key: Optional[str]) -> Optional[str]:
        return (
            api_key
            or os.getenv("AICLIP_VISION_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )

    def _resolve_model(self, model: Optional[str]) -> str:
        return model or os.getenv("AICLIP_VISION_MODEL") or os.getenv("OPENAI_MODEL") or "qwen3-vl-plus"

    def _infer_media_type(self, media_path: str, media_type: Optional[str]) -> str:
        if media_type in {"image", "video"}:
            return media_type

        lower = media_path.lower()
        if any(lower.endswith(ext) for ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")):
            return "video"
        return "image"

    def _build_media_ref(self, media_path: str) -> tuple[str, str]:
        candidate = Path(media_path).expanduser()
        if candidate.exists():
            absolute_path = candidate.resolve()
            return f"file://{absolute_path.as_posix()}", "local-file"
        return media_path, "url"

    def _extract_text_and_usage(self, response: Any) -> tuple[str, Dict[str, Any], str | None, Optional[int], str | None]:
        status_code = getattr(response, "status_code", None)
        message = getattr(response, "message", None)

        output = getattr(response, "output", None)
        if output is None and isinstance(response, dict):
            output = response.get("output")

        choices = []
        if output is not None:
            choices = getattr(output, "choices", None) or (output.get("choices") if isinstance(output, dict) else []) or []

        first_choice = choices[0] if choices else None
        first_message = None
        finish_reason = None
        if first_choice is not None:
            if isinstance(first_choice, dict):
                first_message = first_choice.get("message")
                finish_reason = first_choice.get("finish_reason")
            else:
                first_message = getattr(first_choice, "message", None)
                finish_reason = getattr(first_choice, "finish_reason", None)

        content = []
        if first_message is not None:
            if isinstance(first_message, dict):
                content = first_message.get("content") or []
            else:
                content = getattr(first_message, "content", None) or []

        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("text"):
                    chunks.append(str(item.get("text")))
            else:
                text_value = getattr(item, "text", None)
                if text_value:
                    chunks.append(str(text_value))

        usage_obj = getattr(response, "usage", None)
        if usage_obj is None and isinstance(response, dict):
            usage_obj = response.get("usage")
        if usage_obj is None and output is not None:
            usage_obj = getattr(output, "usage", None) or (output.get("usage") if isinstance(output, dict) else None)

        usage: Dict[str, Any]
        if usage_obj is None:
            usage = {}
        elif isinstance(usage_obj, dict):
            usage = usage_obj
        else:
            usage = dict(getattr(usage_obj, "__dict__", {}) or {})

        return "\n".join(chunks).strip(), usage, finish_reason, status_code, message

    def vision_analyze_media(
        self,
        media_path: str,
        prompt: str = "请输出该媒体的关键事件与时间点。",
        media_type: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        fps: float = 2.0,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Analyze image/video with a vision model.

        Args:
            media_path: Public URL or local file path.
            prompt: Instruction for the model.
            media_type: image or video; inferred when omitted.
            model: Vision model name, defaults to AICLIP_VISION_MODEL.
            api_base: DashScope API base URL.
            api_key: API key for the endpoint.
            fps: Video frame sampling rate (video only).
            temperature: Sampling temperature.
            max_tokens: Optional response token cap.
        """
        resolved_key = self._resolve_api_key(api_key)
        if not resolved_key:
            return ToolResult(
                ok=False,
                status="error",
                code="vision_analyze_media.missing_api_key",
                message="AICLIP_VISION_API_KEY or DASHSCOPE_API_KEY is not configured",
                operation="vision_analyze_media",
                error="missing_api_key",
                next_actions=["configure_env"],
            ).to_dict()

        resolved_base = self._resolve_api_base(api_base)
        resolved_model = self._resolve_model(model)
        resolved_type = self._infer_media_type(media_path, media_type)
        media_ref, input_mode = self._build_media_ref(media_path)

        try:
            dashscope = importlib.import_module("dashscope")
            MultiModalConversation = getattr(dashscope, "MultiModalConversation")
        except Exception:
            install_cmd = f'"{sys.executable}" -m pip install dashscope'
            return ToolResult(
                ok=False,
                status="error",
                code="vision_analyze_media.missing_dashscope_sdk",
                message="dashscope SDK is not installed",
                operation="vision_analyze_media",
                error="missing_dashscope_sdk",
                next_actions=["pip_install_dashscope"],
                state={
                    "python_executable": sys.executable,
                    "install_command": install_cmd,
                },
            ).to_dict()

        dashscope.base_http_api_url = resolved_base
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
        last_error: str | None = None
        retry_count = 0
        for attempt in range(self._max_retries + 1):
            try:
                response = MultiModalConversation.call(
                    api_key=resolved_key,
                    model=resolved_model,
                    messages=messages,
                )

                status_code = getattr(response, "status_code", HTTPStatus.OK)
                if status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    retry_count += 1
                    time.sleep(self._retry_base_seconds * (2 ** attempt))
                    continue

                if status_code != HTTPStatus.OK:
                    message_text = getattr(response, "message", "DashScope request failed")
                    if attempt < self._max_retries:
                        retry_count += 1
                        time.sleep(self._retry_base_seconds * (2 ** attempt))
                        continue
                    return ToolResult(
                        ok=False,
                        status="error",
                        code="vision_analyze_media.http_error",
                        message="Vision API call failed",
                        operation="vision_analyze_media",
                        error=str(message_text),
                        state={
                            "api_base": resolved_base,
                            "model": resolved_model,
                            "media_type": resolved_type,
                            "retry_count": retry_count,
                            "status_code": int(status_code),
                        },
                    ).to_dict()

                response_payload = response
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < self._max_retries:
                    retry_count += 1
                    time.sleep(self._retry_base_seconds * (2 ** attempt))
                    continue
                return ToolResult(
                    ok=False,
                    status="error",
                    code="vision_analyze_media.exception",
                    message="Vision analysis raised an exception",
                    operation="vision_analyze_media",
                    error=str(exc),
                    state={
                        "api_base": resolved_base,
                        "model": resolved_model,
                        "media_type": resolved_type,
                        "retry_count": retry_count,
                    },
                ).to_dict()

        if response_payload is None:
            return ToolResult(
                ok=False,
                status="error",
                code="vision_analyze_media.empty_response",
                message="Vision API returned no response",
                operation="vision_analyze_media",
                error=last_error or "empty_payload",
                state={
                    "api_base": resolved_base,
                    "model": resolved_model,
                    "media_type": resolved_type,
                    "retry_count": retry_count,
                },
            ).to_dict()

        text, usage, finish_reason, status_code, response_message = self._extract_text_and_usage(response_payload)
        if not text:
            text = str(response_message or "")

        return ToolResult(
            ok=True,
            status="ok",
            code="vision_analyze_media.ok",
            message="Vision analysis completed",
            operation="vision_analyze_media",
            summary="Vision analysis completed",
            state={
                "api_base": resolved_base,
                "model": resolved_model,
                "media_type": resolved_type,
                "input_mode": input_mode,
                "usage": usage,
                "retry_count": retry_count,
                "status_code": int(status_code) if status_code is not None else None,
                "transport": "dashscope_multimodal_conversation",
            },
            payload={
                "analysis": text,
                "model": resolved_model,
                "finish_reason": finish_reason,
                "usage": usage,
            },
            content=text,
            next_actions=["plan_project_rough_cut", "add_project_comment"],
        ).to_dict()
