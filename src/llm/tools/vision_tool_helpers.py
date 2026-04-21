from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import os


def resolve_api_base(api_base: Optional[str]) -> str:
    value = api_base or os.getenv("AICLIP_VISION_API_BASE") or os.getenv("AICLIP_DASHSCOPE_BASE")
    return (value or "https://dashscope.aliyuncs.com/api/v1").rstrip("/")


def resolve_api_key(api_key: Optional[str]) -> str:
    resolved = api_key or os.getenv("AICLIP_VISION_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
    if not resolved:
        raise EnvironmentError(
            "Vision API key not configured. "
            "Set AICLIP_VISION_API_KEY (or DASHSCOPE_API_KEY) in your .env file."
        )
    return resolved


def resolve_model(model: Optional[str]) -> str:
    return model or os.getenv("AICLIP_VISION_MODEL") or os.getenv("OPENAI_MODEL") or "qwen3-vl-plus"


def infer_media_type(media_path: str, media_type: Optional[str]) -> str:
    if media_type in {"image", "video"}:
        return media_type
    lower = media_path.lower()
    return "video" if any(lower.endswith(ext) for ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")) else "image"


def build_media_ref(media_path: str) -> tuple[str, str]:
    candidate = Path(media_path).expanduser()
    if candidate.exists():
        return f"file://{candidate.resolve().as_posix()}", "local-file"
    return media_path, "url"


def extract_text_and_usage(response: Any) -> tuple[str, Dict[str, Any], str | None, Optional[int], str | None]:
    status_code = getattr(response, "status_code", None)
    message = getattr(response, "message", None)
    output = getattr(response, "output", None)
    if output is None and isinstance(response, dict):
        output = response.get("output")
    choices: list[Any] = getattr(output, "choices", None) or (output.get("choices") if isinstance(output, dict) else []) or [] if output is not None else []
    first_choice = choices[0] if choices else None
    if isinstance(first_choice, dict):
        first_message = first_choice.get("message")
        finish_reason = first_choice.get("finish_reason")
    else:
        first_message = getattr(first_choice, "message", None)
        finish_reason = getattr(first_choice, "finish_reason", None)
    content = first_message.get("content") if isinstance(first_message, dict) else getattr(first_message, "content", None)
    if content is None:
        content = []
    chunks = [str(item.get("text")) for item in content if isinstance(item, dict) and item.get("text")]
    chunks.extend(str(getattr(item, "text")) for item in content if not isinstance(item, dict) and getattr(item, "text", None))
    usage_obj = getattr(response, "usage", None) or (response.get("usage") if isinstance(response, dict) else None) or (getattr(output, "usage", None) if output is not None else None) or ((output.get("usage") if isinstance(output, dict) else None) if output is not None else None)
    usage = {} if usage_obj is None else usage_obj if isinstance(usage_obj, dict) else dict(getattr(usage_obj, "__dict__", {}) or {})
    return "\n".join(chunks).strip(), usage, finish_reason, status_code, message
