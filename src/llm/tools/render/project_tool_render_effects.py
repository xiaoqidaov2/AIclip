from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
from moviepy import ImageClip  # type: ignore[import-untyped]
from src.editor_core.project import SubtitleCue


class ProjectToolRenderEffectsMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _apply_slide_anim(self, clip: Any, params: Dict[str, Any], x_pos: int, y_pos: int, anchor_time: float, mode: str) -> Any:
        direction = str(params.get("direction", "bottom")).lower()
        duration = float(params.get("duration", 0.3))
        distance = int(params.get("distance", 40))
        def _pos(t: float) -> tuple[int, int]:
            progress = min(1.0, max(0.0, (t - anchor_time) / duration)) if mode == "in" and duration > 0 else min(1.0, max(0.0, (t - (anchor_time - duration)) / duration)) if duration > 0 else 1.0
            ease = progress * progress * (3 - 2 * progress)
            slide = int(distance * (1.0 - ease)) if mode == "in" else int(distance * ease)
            return (x_pos, y_pos + slide) if direction == "bottom" else (x_pos, y_pos - slide) if direction == "top" else (x_pos - slide, y_pos) if direction == "left" else (x_pos + slide, y_pos) if direction == "right" else (x_pos, y_pos)
        try:
            return self._clip_call(clip, "with_position", _pos)
        except Exception:
            return self._clip_call(clip, "with_position", (x_pos, y_pos))

    def _apply_scale_in(self, clip: Any, params: Dict[str, Any], x_pos: int, y_pos: int) -> Any:
        duration = float(params.get("duration", 0.3))
        base_w, base_h = getattr(clip, "size", (0, 0))
        def _progress(t: float) -> float:
            progress = min(1.0, max(0.0, t / duration)) if duration > 0 else 1.0
            return progress * progress * (3 - 2 * progress)
        def _scale(t: float) -> tuple[int, int]:
            ease = _progress(t)
            return (max(1, int(round(base_w * max(0.01, ease)))), max(1, int(round(base_h * max(0.01, ease)))))
        def _position(t: float) -> tuple[int, int]:
            ease = _progress(t)
            width = max(1, int(round(base_w * max(0.01, ease))))
            height = max(1, int(round(base_h * max(0.01, ease))))
            return (x_pos + max(0, (base_w - width) // 2), y_pos + max(0, (base_h - height) // 2))
        try:
            clip = self._clip_call(clip, "resized", _scale)
            return self._clip_call(clip, "with_position", _position)
        except Exception:
            return clip

    def _make_typewriter_clips(self, cue: SubtitleCue, effective_width: int, font_path: Optional[str], font_size: int, subtitle_color: str, params: Dict[str, Any], base_video: Any, project: Optional[Any] = None) -> list[Any]:
        chars_per_second = float(params.get("chars_per_second", 20))
        full_text = cue.text
        if len(full_text) == 0 or chars_per_second <= 0:
            return []
        clips: list[Any] = []
        char_duration = 1.0 / chars_per_second
        reveal_end = cue.start
        for n in range(1, len(full_text) + 1):
            t_start = cue.start + (n - 1) * char_duration
            t_end = min(cue.start + n * char_duration, cue.end)
            if t_start >= cue.end:
                break
            image = self._make_subtitle_image(full_text[:n], effective_width, font_path, font_size, subtitle_color, cue.spans, cue.effects)
            subtitle_clip = ImageClip(np.array(image))
            subtitle_clip = self._set_clip_duration(subtitle_clip, max(0.01, t_end - t_start))
            subtitle_clip = self._clip_call(subtitle_clip, "with_start", t_start)
            subtitle_clip = self._clip_call(subtitle_clip, "with_end", t_end)
            y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
            x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))
            subtitle_clip = self._clip_call(subtitle_clip, "with_position", (x_pos, y_pos))
            clips.append(subtitle_clip)
            reveal_end = t_end
        if reveal_end < cue.end:
            image = self._make_subtitle_image(full_text, effective_width, font_path, font_size, subtitle_color, cue.spans, cue.effects)
            tail_clip = ImageClip(np.array(image))
            tail_clip = self._set_clip_duration(tail_clip, max(0.01, cue.end - reveal_end))
            tail_clip = self._clip_call(tail_clip, "with_start", reveal_end)
            tail_clip = self._clip_call(tail_clip, "with_end", cue.end)
            y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
            x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))
            tail_clip = self._clip_call(tail_clip, "with_position", (x_pos, y_pos))
            clips.append(tail_clip)
        return clips
