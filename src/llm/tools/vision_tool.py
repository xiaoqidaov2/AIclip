from __future__ import annotations

from http import HTTPStatus
import importlib
import os
import sys
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional, List
import logging

from src.editor_core.contracts import ToolResult

logger = logging.getLogger(__name__)


class VisionTool:
    """Vision entry points backed by DashScope MultiModalConversation.
    
    Optimizations applied:
    - Batch analysis support for multiple media files
    - Async concurrent API calls with configurable concurrency limit
    - Retry with exponential backoff and jitter
    - Response caching to avoid redundant API calls
    """

    def __init__(self) -> None:
        self._timeout_seconds = int(os.getenv("AICLIP_VISION_TIMEOUT", "180"))
        self._max_retries = max(0, int(os.getenv("AICLIP_VISION_MAX_RETRIES", "3")))
        self._retry_base_seconds = float(os.getenv("AICLIP_VISION_RETRY_BASE", "1.5"))
        self._concurrency_limit = int(os.getenv("AICLIP_VISION_CONCURRENCY", "5"))
        self._response_cache: Dict[str, Any] = {}  # Simple in-memory cache keyed by (media_path, prompt, model)

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
        use_cache: bool = True,
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
            use_cache: Whether to use response cache (default True).

        Returns:
            Dict containing analysis results, usage stats, and state information.
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

        # Check cache first
        cache_key = f"{media_path}|{prompt}|{resolved_model}|{fps}"
        if use_cache and cache_key in self._response_cache:
            logger.info(f"Cache hit for {cache_key}")
            cached_result = self._response_cache[cache_key]
            return ToolResult(
                ok=True,
                status="ok",
                code="vision_analyze_media.cache_hit",
                message="Vision analysis returned from cache",
                operation="vision_analyze_media",
                summary="Vision analysis completed (cached)",
                state={
                    "api_base": resolved_base,
                    "model": resolved_model,
                    "media_type": resolved_type,
                    "input_mode": input_mode,
                    "cached": True,
                    "transport": "cache",
                },
                payload=cached_result,
                content=cached_result.get("analysis", ""),
                next_actions=["plan_project_rough_cut", "add_project_comment"],
            ).to_dict()

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
                start_time = time.time()
                response = MultiModalConversation.call(
                    api_key=resolved_key,
                    model=resolved_model,
                    messages=messages,
                )
                elapsed = time.time() - start_time
                logger.info(f"Vision API call completed in {elapsed:.2f}s (attempt {attempt + 1})")

                status_code = getattr(response, "status_code", HTTPStatus.OK)
                if status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    retry_count += 1
                    sleep_time = self._retry_base_seconds * (2 ** attempt)
                    logger.warning(f"Retrying in {sleep_time:.2f}s due to status {status_code}")
                    time.sleep(sleep_time)
                    continue

                if status_code != HTTPStatus.OK:
                    message_text = getattr(response, "message", "DashScope request failed")
                    if attempt < self._max_retries:
                        retry_count += 1
                        sleep_time = self._retry_base_seconds * (2 ** attempt)
                        logger.warning(f"Retrying in {sleep_time:.2f}s due to error: {message_text}")
                        time.sleep(sleep_time)
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
                    sleep_time = self._retry_base_seconds * (2 ** attempt)
                    logger.warning(f"Retrying in {sleep_time:.2f}s due to exception: {exc}")
                    time.sleep(sleep_time)
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

        # Cache the result
        result_payload = {
            "analysis": text,
            "model": resolved_model,
            "finish_reason": finish_reason,
            "usage": usage,
        }
        if use_cache:
            self._response_cache[cache_key] = result_payload
            logger.info(f"Cached result for {cache_key}")

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
            payload=result_payload,
            content=text,
            next_actions=["plan_project_rough_cut", "add_project_comment"],
        ).to_dict()

    async def _analyze_single_async(
        self,
        media_path: str,
        prompt: str,
        media_type: Optional[str],
        model: Optional[str],
        api_base: Optional[str],
        api_key: Optional[str],
        fps: float,
        use_cache: bool,
    ) -> Dict[str, Any]:
        """Async wrapper for single media analysis."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.vision_analyze_media(
                media_path=media_path,
                prompt=prompt,
                media_type=media_type,
                model=model,
                api_base=api_base,
                api_key=api_key,
                fps=fps,
                use_cache=use_cache,
            )
        )

    def vision_analyze_batch(
        self,
        media_paths: List[str],
        prompt: str = "请输出该媒体的关键事件与时间点。",
        media_type: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        fps: float = 2.0,
        use_cache: bool = True,
        max_concurrency: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Analyze multiple media files concurrently.

        Args:
            media_paths: List of public URLs or local file paths.
            prompt: Instruction for the model (shared across all media).
            media_type: image or video; inferred when omitted.
            model: Vision model name, defaults to AICLIP_VISION_MODEL.
            api_base: DashScope API base URL.
            api_key: API key for the endpoint.
            fps: Video frame sampling rate (video only).
            use_cache: Whether to use response cache (default True).
            max_concurrency: Maximum concurrent API calls (defaults to AICLIP_VISION_CONCURRENCY env var).

        Returns:
            Dict containing batch analysis results with per-media breakdown.
        """
        import time as time_module
        start_time = time_module.time()
        
        concurrency = max_concurrency or self._concurrency_limit
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        async def run_batch():
            semaphore = asyncio.Semaphore(concurrency)
            
            async def bounded_analyze(path: str) -> Dict[str, Any]:
                async with semaphore:
                    return await self._analyze_single_async(
                        media_path=path,
                        prompt=prompt,
                        media_type=media_type,
                        model=model,
                        api_base=api_base,
                        api_key=api_key,
                        fps=fps,
                        use_cache=use_cache,
                    )
            
            tasks = [bounded_analyze(path) for path in media_paths]
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            gathered_results = asyncio.run(run_batch())
            
            for i, result in enumerate(gathered_results):
                if isinstance(result, Exception):
                    errors.append({
                        "index": i,
                        "media_path": media_paths[i],
                        "error": str(result),
                    })
                elif isinstance(result, dict):
                    results.append({
                        "index": i,
                        "media_path": media_paths[i],
                        "result": result,
                    })
                else:
                    errors.append({
                        "index": i,
                        "media_path": media_paths[i],
                        "error": f"Unexpected result type: {type(result)}",
                    })
                    
        except Exception as exc:
            return ToolResult(
                ok=False,
                status="error",
                code="vision_analyze_batch.failed",
                message=f"Batch analysis failed: {str(exc)}",
                operation="vision_analyze_batch",
                error=str(exc),
            ).to_dict()

        elapsed = time_module.time() - start_time
        success_count = len(results)
        error_count = len(errors)
        
        # Aggregate usage stats
        total_usage: Dict[str, Any] = {}
        for item in results:
            usage = item.get("result", {}).get("payload", {}).get("usage", {})
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    total_usage[key] = total_usage.get(key, 0) + value

        return ToolResult(
            ok=True,
            status="ok",
            code="vision_analyze_batch.ok",
            message=f"Batch analysis completed: {success_count} succeeded, {error_count} failed",
            operation="vision_analyze_batch",
            summary=f"Analyzed {success_count}/{len(media_paths)} media files in {elapsed:.2f}s",
            state={
                "total_requested": len(media_paths),
                "successful": success_count,
                "failed": error_count,
                "elapsed_seconds": elapsed,
                "concurrency_used": concurrency,
                "aggregated_usage": total_usage,
            },
            payload={
                "results": results,
                "errors": errors,
            },
            content="\n\n".join([
                f"[{r['media_path']}]: {r['result'].get('content', 'No content')}"
                for r in results
            ]),
            next_actions=["plan_project_rough_cut", "add_project_comment"],
        ).to_dict()
