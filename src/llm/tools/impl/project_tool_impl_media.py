from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image
from moviepy import ImageClip, VideoFileClip  # type: ignore[import-untyped]

from src.editor_core.project import Asset, Clip, Project
from src.editor_core.store import ProjectStore


class ProjectToolMediaMixin:
    store: ProjectStore

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _clip_call(self, clip: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(clip, method_name, None)
        if callable(method):
            return method(*args, **kwargs)
        return clip

    def _subclip(self, clip: Any, start: float, end: float) -> Any:
        for method_name in ("subclipped", "subclip"):
            method = getattr(clip, method_name, None)
            if callable(method):
                return method(start, end)
        raise AttributeError("moviepy clip does not support subclip extraction")

    def _set_clip_duration(self, clip: Any, duration: float) -> Any:
        for method_name in ("with_duration", "set_duration"):
            updated = self._clip_call(clip, method_name, duration)
            if updated is not clip or hasattr(updated, method_name):
                return updated
        return clip

    def _set_clip_range(self, clip: Any, start: float, end: float) -> Any:
        for start_method, end_method in (("with_start", "with_end"), ("set_start", "set_end")):
            updated = self._clip_call(clip, start_method, start)
            updated = self._clip_call(updated, end_method, end)
            if updated is not clip or hasattr(updated, start_method):
                return updated
        return clip

    def _asset_for_clip(self, project: Project, clip: Clip) -> Asset:
        asset = project.find_asset(clip.asset_id)
        if asset is None:
            raise ValueError(f"Asset not found for clip: {clip.asset_id}")
        return asset

    def _asset_path_for_clip(self, project: Project, clip: Clip, project_path: str) -> Path:
        asset = self._asset_for_clip(project, clip)
        return self.store.resolve_asset_path(asset.path, project_path)

    def _asset_media_type(self, asset: Asset, asset_path: Path) -> str:
        if asset.media_type in {"video", "image", "audio"}:
            return asset.media_type
        suffix = asset_path.suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            return "image"
        if suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}:
            return "audio"
        return "video"

    def _project_canvas(self, project: Project, project_path: str) -> tuple[int, int, float]:
        size = project.metadata.get("source_media_size") or project.metadata.get("size")
        if not size:
            size = project.assets[0].metadata.get("size") if project.assets else None
        width = int(size[0]) if isinstance(size, list) and len(size) >= 2 else 1080
        height = int(size[1]) if isinstance(size, list) and len(size) >= 2 else 1920
        fps = float(project.timeline.fps or project.metadata.get("source_media_fps") or 30.0)
        return width, height, fps

    def _project_source_duration(
        self, project: Project, project_path: Optional[str] = None
    ) -> Optional[float]:
        metadata_duration = project.metadata.get("source_media_duration")
        if isinstance(metadata_duration, (int, float)) and float(metadata_duration) > 0:
            return float(metadata_duration)
        asset_durations = [
            float(asset.duration)
            for asset in project.assets
            if isinstance(asset.duration, (int, float)) and float(asset.duration) > 0
        ]
        if asset_durations:
            return max(asset_durations)
        if not project_path:
            return None
        source_path = self._resolve_media_path(project, project_path=project_path)
        if source_path is None:
            return None
        try:
            media_info = self._probe_media(source_path)
        except Exception:
            media_info = None
        if not media_info:
            return None
        duration = media_info.get("duration")
        return float(duration) if isinstance(duration, (int, float)) and float(duration) > 0 else None

    def _transform_video_clip(self, media_clip: Any, clip: Clip) -> Any:
        transform = dict(clip.transform or {})
        scale = transform.get("scale")
        if isinstance(scale, (int, float)) and scale > 0:
            media_clip = self._clip_call(media_clip, "resized", float(scale))
        opacity = transform.get("opacity")
        if isinstance(opacity, (int, float)):
            media_clip = self._clip_call(media_clip, "with_opacity", float(opacity))
        if transform.get("x") is not None or transform.get("y") is not None:
            media_clip = self._clip_call(
                media_clip,
                "with_position",
                (int(transform.get("x", 0)), int(transform.get("y", 0))),
            )
        return media_clip

    def _build_timeline_video_clip(
        self, project: Project, clip: Clip, project_path: str
    ) -> tuple[Any, list[Any]]:
        asset = self._asset_for_clip(project, clip)
        asset_path = self._asset_path_for_clip(project, clip, project_path)
        media_type = self._asset_media_type(asset, asset_path)
        opened: list[Any] = []
        if media_type == "image":
            image = Image.open(asset_path).convert("RGBA")
            opened.append(image)
            media_clip = ImageClip(np.array(image))
            opened.append(media_clip)
            media_clip = self._set_clip_duration(media_clip, max(0.01, clip.end - clip.start))
        else:
            media_clip = self._build_video_clip(asset_path, clip, opened)
        media_clip = self._set_clip_range(media_clip, float(clip.start), float(clip.end))
        media_clip = self._transform_video_clip(media_clip, clip)
        return media_clip, opened

    def _build_video_clip(self, asset_path: Path, clip: Clip, opened: list[Any]) -> Any:
        source = VideoFileClip(str(asset_path))
        opened.append(source)
        source_in = float(clip.source_in or 0.0)
        source_duration = float(getattr(source, "duration", clip.end - clip.start) or (clip.end - clip.start))
        requested_source_out = float(clip.source_out if clip.source_out is not None else source_duration)
        source_out = min(requested_source_out, source_duration)
        if source_out <= source_in:
            source_out = min(source_duration, source_in + max(0.01, float(clip.end - clip.start)))
        media_clip = self._subclip(source, source_in, source_out)
        opened.append(media_clip)
        if getattr(clip, "speed", 1.0) not in (None, 1.0):
            media_clip = self._clip_call(media_clip, "with_speed_scaled", clip.speed)
        return media_clip