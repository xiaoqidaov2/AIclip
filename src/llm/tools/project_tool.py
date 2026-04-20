from __future__ import annotations

import json
import math
import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont

from src.editor_core.commands import (
    AddAssetCommand,
    AddClipCommand,
    AddAudioStemCommand,
    AddCommentCommand,
    AddEffectCommand,
    AddSubtitleCueCommand,
    AddSubtitleSpanCommand,
    LockCommentCommand,
    RemoveAudioStemCommand,
    RemoveCommentCommand,
    RemoveEffectCommand,
    RemoveSubtitleCueCommand,
    RemoveSubtitleSpanCommand,
    RemoveSubtitleEffectCommand,
    SetClipSpeedCommand,
    SetExportPresetCommand,
    SetProjectMetadataCommand,
    SetSubtitleEffectCommand,
    TrimClipCommand,
    UpdateCommentCommand,
    UpdateEffectCommand,
    UpdateAudioStemCommand,
    UpdateSubtitleCueCommand,
    UpdateSubtitleSpanCommand,
)
from src.editor_core.contracts import ArtifactRef, RenderState, ToolResult, ValidationSnapshot
from src.editor_core.project import Asset, AudioStem, Clip, Comment, Effect, ExportPreset, Project, SubtitleCue, SubtitleEffect, SubtitleSpan, Timeline, Track
from src.editor_core.store import ProjectStore
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoFileClip, concatenate_videoclips
from moviepy.video.fx import CrossFadeIn, CrossFadeOut


class ProjectTool:
    """Project-level editing entry points backed by editor_core."""

    def __init__(self) -> None:
        self.store = ProjectStore()
        self._opencc_converter = None
        self._opencc_checked = False

    def _project_counts(self, project: Project) -> Dict[str, Any]:
        return {
            "asset_count": len(project.assets),
            "track_count": len(project.timeline.tracks),
            "subtitle_count": len(project.subtitles),
            "audio_stem_count": len(project.audio_stems),
            "effect_count": len(project.effects),
            "comment_count": len(project.comments),
            "export_preset_count": len(project.export_presets),
        }

    def _project_summary_payload(self, project: Project, project_path: str) -> Dict[str, Any]:
        track_summaries = []
        for track in project.timeline.tracks:
            track_summaries.append(
                {
                    "id": track.id,
                    "kind": track.kind,
                    "name": track.name,
                    "clip_count": len(track.clips),
                    "visible": track.visible,
                    "locked": track.locked,
                    "muted": track.muted,
                }
            )

        subtitle_languages = sorted({cue.language for cue in project.subtitles if cue.language})
        return {
            "project_path": str(Path(project_path)),
            "project_id": project.id,
            "project_name": project.name,
            "project_version": project.version,
            "timeline_duration": float(project.timeline.duration or 0.0),
            "timeline_fps": float(project.timeline.fps or 0.0) if project.timeline.fps else None,
            "tracks": track_summaries,
            "subtitle_languages": subtitle_languages,
            "has_subtitles": bool(project.subtitles),
            "has_audio_track": any(item.kind == "audio" and item.clips for item in project.timeline.tracks),
            "source_media_path": project.metadata.get("source_media_path"),
            **self._project_counts(project),
        }

    def _clip_listing_entry(self, project: Project, track: Track, clip: Clip) -> Dict[str, Any]:
        asset = project.find_asset(clip.asset_id)
        return {
            "clip_id": clip.id,
            "track_id": track.id,
            "track_kind": track.kind,
            "track_name": track.name,
            "asset_id": clip.asset_id,
            "asset_path": asset.path if asset is not None else None,
            "asset_media_type": asset.media_type if asset is not None else None,
            "start": float(clip.start),
            "end": float(clip.end),
            "duration": float(clip.end - clip.start),
            "source_in": float(clip.source_in),
            "source_out": float(clip.source_out) if clip.source_out is not None else None,
            "speed": float(clip.speed),
            "transform": dict(clip.transform or {}),
            "metadata": dict(clip.metadata or {}),
        }

    def _subtitle_search_entry(self, cue: SubtitleCue) -> Dict[str, Any]:
        return {
            "subtitle_id": cue.id,
            "start": float(cue.start),
            "end": float(cue.end),
            "duration": float(cue.end - cue.start),
            "text": cue.text,
            "speaker": cue.speaker,
            "language": cue.language,
            "track_id": cue.track_id,
            "position": cue.position,
            "span_count": len(cue.spans),
        }

    def _resolve_media_path(self, project: Project, media_path: Optional[str] = None, project_path: Optional[str] = None) -> Optional[Path]:
        anchor = project_path or project.metadata.get("project_path") or "project.json"
        if media_path:
            candidate = self.store.resolve_asset_path(media_path, anchor)
            if candidate.exists():
                return candidate

        source_media = project.metadata.get("source_media_path")
        if isinstance(source_media, str):
            candidate = self.store.resolve_asset_path(source_media, anchor)
            if candidate.exists():
                return candidate

        for asset in project.assets:
            candidate = self.store.resolve_asset_path(asset.path, anchor)
            if candidate.exists():
                return candidate

        return None

    def _project_main_track(self, project: Project, track_id: Optional[str] = None) -> Optional[Track]:
        if track_id:
            track = project.find_track(track_id)
            if track is not None:
                return track

        for track in project.timeline.tracks:
            if track.kind in {"video", "audio"}:
                return track
        return project.timeline.tracks[0] if project.timeline.tracks else None

    def _merge_intervals(self, intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
        cleaned = [(float(start), float(end)) for start, end in intervals if end > start]
        if not cleaned:
            return []

        cleaned.sort(key=lambda item: item[0])
        merged: list[tuple[float, float]] = [cleaned[0]]
        for start, end in cleaned[1:]:
            prev_start, prev_end = merged[-1]
            if start <= prev_end:
                merged[-1] = (prev_start, max(prev_end, end))
            else:
                merged.append((start, end))
        return merged

    def _remap_time(self, time_value: float, intervals: list[tuple[float, float]]) -> float:
        elapsed = 0.0
        for start, end in intervals:
            if time_value < start:
                return elapsed
            if start <= time_value <= end:
                return elapsed + (time_value - start)
            elapsed += max(0.0, end - start)
        return elapsed

    def _subtitle_intervals(self, subtitles: list[SubtitleCue]) -> list[tuple[float, float]]:
        return self._merge_intervals([(cue.start, cue.end) for cue in subtitles])

    def _normalize_subtitle_spans(
        self,
        cue_id: str,
        spans: list[dict[str, Any] | SubtitleSpan],
    ) -> list[SubtitleSpan]:
        normalized: list[SubtitleSpan] = []
        for index, item in enumerate(spans, start=1):
            span = item if isinstance(item, SubtitleSpan) else SubtitleSpan.from_dict(item)
            if not span.id:
                span.id = f"{cue_id}_span_{index:03d}"
            span.text = self._normalize_transcribed_text(span.text)
            normalized.append(span)
        return normalized

    def _coerce_json_array(self, value: Any, field_name: str) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValueError(f"{field_name} must be a list")
            return parsed
        raise ValueError(f"{field_name} must be a list or JSON list string")

    def _coerce_json_object(self, value: Any, field_name: str) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError(f"{field_name} must be an object")
            return parsed
        raise ValueError(f"{field_name} must be a dict or JSON object string")

    def _coerce_subtitle_style_entries(self, value: Any) -> list[Dict[str, Any]]:
        entries = self._coerce_json_array(value, "entries")
        normalized: list[Dict[str, Any]] = []
        for index, item in enumerate(entries, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"entries[{index}] must be an object")
            subtitle_id = item.get("subtitle_id")
            if not isinstance(subtitle_id, str) or not subtitle_id.strip():
                raise ValueError(f"entries[{index}].subtitle_id is required")

            normalized_entry = dict(item)
            spans = normalized_entry.get("spans")
            if spans is not None and not isinstance(spans, list):
                raise ValueError(f"entries[{index}].spans must be a list")

            effects = normalized_entry.get("effects")
            if effects is not None:
                if not isinstance(effects, list):
                    raise ValueError(f"entries[{index}].effects must be a list")
                for effect_index, effect in enumerate(effects, start=1):
                    if not isinstance(effect, dict):
                        raise ValueError(f"entries[{index}].effects[{effect_index}] must be an object")
                    kind = effect.get("kind")
                    if not isinstance(kind, str) or not kind.strip():
                        raise ValueError(f"entries[{index}].effects[{effect_index}].kind is required")
                    parameters = effect.get("parameters")
                    if parameters is not None and not isinstance(parameters, dict):
                        raise ValueError(f"entries[{index}].effects[{effect_index}].parameters must be an object")
            normalized.append(normalized_entry)
        return normalized

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

    def _project_source_duration(self, project: Project, project_path: Optional[str] = None) -> Optional[float]:
        metadata_duration = project.metadata.get("source_media_duration")
        if isinstance(metadata_duration, (int, float)) and float(metadata_duration) > 0:
            return float(metadata_duration)

        asset_durations = [float(asset.duration) for asset in project.assets if isinstance(asset.duration, (int, float)) and float(asset.duration) > 0]
        if asset_durations:
            return max(asset_durations)

        if project_path:
            source_path = self._resolve_media_path(project, project_path=project_path)
            if source_path is not None:
                try:
                    media_info = self._probe_media(source_path)
                except Exception:
                    media_info = None
                if media_info:
                    duration = media_info.get("duration")
                    if isinstance(duration, (int, float)) and float(duration) > 0:
                        return float(duration)
        return None

    def _transform_video_clip(self, media_clip: Any, clip: Clip) -> Any:
        transform = dict(clip.transform or {})
        scale = transform.get("scale")
        if isinstance(scale, (int, float)) and scale > 0:
            media_clip = self._clip_call(media_clip, "resized", float(scale))

        opacity = transform.get("opacity")
        if isinstance(opacity, (int, float)):
            media_clip = self._clip_call(media_clip, "with_opacity", float(opacity))

        if transform.get("x") is not None or transform.get("y") is not None:
            x_pos = int(transform.get("x", 0))
            y_pos = int(transform.get("y", 0))
            media_clip = self._clip_call(media_clip, "with_position", (x_pos, y_pos))
        return media_clip

    def _build_timeline_video_clip(self, project: Project, clip: Clip, project_path: str) -> tuple[Any, list[Any]]:
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

        media_clip = self._set_clip_range(media_clip, float(clip.start), float(clip.end))
        media_clip = self._transform_video_clip(media_clip, clip)
        return media_clip, opened

    def _make_subtitle_image(
        self,
        text: str,
        width: int,
        font_path: Optional[str],
        font_size: int,
        color: str,
        spans: Optional[list[SubtitleSpan]] = None,
        effects: Optional[list[SubtitleEffect]] = None,
    ) -> Image.Image:
        fx_map: Dict[str, Dict[str, Any]] = {}
        for fx in (effects or []):
            fx_map[fx.kind] = fx.parameters

        image = Image.new("RGBA", (width, max(1, font_size * 4)), (0, 0, 0, 0))
        bg_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_layer)
        text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        
        # We only use 'draw' for measurements when needed
        draw = ImageDraw.Draw(image)
        font = self._load_font(font_path, font_size)
        # pixel-safe wrap margin: leave a small gutter on each side
        _wrap_max_px = max(1, width - font_size)

        glow_layers: Dict[int, Image.Image] = {}
        glow_draws: Dict[int, ImageDraw.ImageDraw] = {}

        def _get_glow_draw(r: int) -> ImageDraw.ImageDraw:
            if r not in glow_layers:
                glow_layers[r] = Image.new("RGBA", image.size, (0, 0, 0, 0))
                glow_draws[r] = ImageDraw.Draw(glow_layers[r])
            return glow_draws[r]

        def _resize_layers(new_size):
            nonlocal image, bg_layer, bg_draw, text_layer, text_draw, draw
            image = Image.new("RGBA", new_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            bg_layer = Image.new("RGBA", new_size, (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_layer)
            text_layer = Image.new("RGBA", new_size, (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            
            for r in list(glow_layers.keys()):
                old_img = glow_layers[r]
                new_img = Image.new("RGBA", new_size, (0, 0, 0, 0))
                new_img.paste(old_img, (0, 0))
                glow_layers[r] = new_img
                glow_draws[r] = ImageDraw.Draw(new_img)

        def _default_outline_offsets(width: int = 2) -> list[tuple[int, int]]:
            return [
                (dx, dy)
                for dx in range(-width, width + 1)
                for dy in range(-width, width + 1)
                if dx != 0 or dy != 0
            ]

        if spans:
            full_text = self._sanitize_text(text)
            default_style = {
                "color": color,
                "outline": fx_map.get("outline"),
                "glow": fx_map.get("glow"),
                "bold": False,
                "underline": False,
            }
            char_styles: List[Dict[str, Any]] = [dict(default_style) for _ in full_text]
            covered_cursor = 0

            for span in spans:
                sanitized_span_text = self._sanitize_text(span.text)
                if not sanitized_span_text:
                    continue
                span_color = span.color or color
                span_fx = getattr(span, "effects", [])
                span_fx_map = {fx.kind: fx.parameters for fx in span_fx}
                style = {
                    "color": span_color,
                    "outline": span_fx_map.get("outline", fx_map.get("outline")),
                    "glow": span_fx_map.get("glow", fx_map.get("glow")),
                    "bold": bool(getattr(span, "bold", False)),
                    "underline": bool(getattr(span, "underline", False)),
                }

                start_idx, end_idx = self._find_span_range(
                    full_text,
                    sanitized_span_text,
                    covered_cursor=covered_cursor,
                    single_span=len(spans) == 1,
                )
                if start_idx < 0:
                    continue

                for char_index in range(start_idx, end_idx):
                    char_styles[char_index] = dict(style)
                covered_cursor = end_idx

            wrapped_lines = self._wrap_by_pixel_width(full_text, font, _wrap_max_px, draw) or [full_text]

            sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
            line_height = (sample_bbox[3] - sample_bbox[1]) + 6
            total_h = line_height * len(wrapped_lines)

            if total_h > image.height or total_h < image.height // 2:
                new_size = (width, max(total_h + font_size // 2, font_size * 2))
                _resize_layers(new_size)

            if "background_box" in fx_map:
                self._draw_background_box(bg_draw, image.width, image.height, fx_map["background_box"])

            start_y = max(0, (image.height - total_h) // 2)
            full_idx = 0

            for line in wrapped_lines:
                line_bbox = draw.textbbox((0, 0), line, font=font)
                line_w = line_bbox[2] - line_bbox[0]
                cx = max(0, (width - line_w) // 2)
                cy = start_y

                i = 0
                while i < len(line):
                    fpos = full_idx + i
                    seg_style = char_styles[fpos] if fpos < len(char_styles) else {
                        "color": color,
                        "outline": fx_map.get("outline"),
                        "glow": fx_map.get("glow"),
                        "bold": False,
                        "underline": False,
                    }
                    j = i + 1
                    while j < len(line):
                        fpos_j = full_idx + j
                        if fpos_j >= len(char_styles) or char_styles[fpos_j] != seg_style:
                            break
                        j += 1
                    seg_text = line[i:j]

                    outline_p = seg_style["outline"]
                    if outline_p is not None: # explicitly using outline
                        shadow = outline_p.get("color", "black")
                        ow = int(outline_p.get("width", 2))
                        o_offsets = [(dx, dy) for dx in range(-ow, ow + 1) for dy in range(-ow, ow + 1) if dx != 0 or dy != 0]
                    else: # default shadow fallback
                        shadow = "black"
                        o_offsets = _default_outline_offsets(2)

                    for dx, dy in o_offsets:
                        text_draw.text((cx + dx, cy + dy), seg_text, font=font, fill=shadow)

                    fill_offsets = [(0, 0)]
                    if seg_style.get("bold"):
                        fill_offsets.extend([(1, 0), (0, 1)])
                    for dx, dy in fill_offsets:
                        text_draw.text((cx + dx, cy + dy), seg_text, font=font, fill=seg_style["color"])

                    glow_p = seg_style["glow"]
                    if glow_p:
                        r = int(glow_p.get("radius", 4))
                        gc = glow_p.get("color", "white")
                        gr, gg, gb, ga = self._parse_color(gc, 255)
                        _get_glow_draw(r).text((cx, cy), seg_text, font=font, fill=(gr, gg, gb, ga))

                    if seg_style.get("underline"):
                        seg_width = int(draw.textlength(seg_text, font=font))
                        underline_y = cy + (font.size if hasattr(font, "size") else font_size) + 1
                        text_draw.line(
                            [(cx, underline_y), (cx + max(1, seg_width), underline_y)],
                            fill=seg_style["color"],
                            width=2 if seg_style.get("bold") else 1,
                        )

                    # Advance cx using textlength instead of textbbox to preserve kerning/spacing
                    cx += int(draw.textlength(seg_text, font=font))
                    i = j

                full_idx += len(line)
                while full_idx < len(full_text) and full_text[full_idx] == " ":
                    full_idx += 1

                start_y += line_height
        else:
            wrapped = "\n".join(self._wrap_by_pixel_width(self._sanitize_text(text), font, _wrap_max_px, draw))
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6, align="center")
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = max(0, (width - text_w) // 2)
            y = max(0, (image.height - text_h) // 2)

            if text_h > image.height or text_h < image.height // 2:
                new_size = (width, max(text_h + font_size // 2, font_size * 2))
                _resize_layers(new_size)
                y = max(0, (image.height - text_h) // 2)

            if "background_box" in fx_map:
                self._draw_background_box(bg_draw, image.width, image.height, fx_map["background_box"])

            outline_p = fx_map.get("outline")
            if outline_p is not None:
                shadow = outline_p.get("color", "black")
                ow = int(outline_p.get("width", 2))
                o_offsets = [(dx, dy) for dx in range(-ow, ow + 1) for dy in range(-ow, ow + 1) if dx != 0 or dy != 0]
            else:
                shadow = "black"
                o_offsets = _default_outline_offsets(2)

            for dx, dy in o_offsets:
                text_draw.multiline_text((x + dx, y + dy), wrapped, font=font, fill=shadow, spacing=6, align="center")
            text_draw.multiline_text((x, y), wrapped, font=font, fill=color, spacing=6, align="center")

            glow_p = fx_map.get("glow")
            if glow_p:
                r = int(glow_p.get("radius", 4))
                gc = glow_p.get("color", "white")
                gr, gg, gb, ga = self._parse_color(gc, 255)
                # Note: spacing is 6, align is center.
                _get_glow_draw(r).multiline_text((x, y), wrapped, font=font, fill=(gr, gg, gb, ga), spacing=6, align="center")

        from PIL import ImageFilter
        final_image = bg_layer
        for r, g_img in glow_layers.items():
            blurred = g_img.filter(ImageFilter.GaussianBlur(r))
            final_image = Image.alpha_composite(final_image, blurred)
        
        final_image = Image.alpha_composite(final_image, text_layer)
        return final_image

    def _parse_color(self, color_str: str, default_a: int = 255) -> tuple[int, int, int, int]:
        c_str = color_str.strip().lower()
        if c_str.startswith("rgba"):
            inner = c_str[4:].strip("() ")
            parts = [p.strip() for p in inner.split(',')]
            if len(parts) >= 3:
                try:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    a = default_a
                    if len(parts) >= 4:
                        if "." in parts[3] or float(parts[3]) <= 1.0:
                            a = int(float(parts[3]) * 255)
                        else:
                            a = int(parts[3])
                    return (r, g, b, a)
                except Exception:
                    pass
        from PIL import ImageColor
        try:
            rgba = ImageColor.getrgb(c_str)
            if len(rgba) == 4:
                return (rgba[0], rgba[1], rgba[2], rgba[3])
            return (rgba[0], rgba[1], rgba[2], default_a)
        except Exception:
            return (255, 255, 255, default_a)

    def _draw_background_box(
        self,
        draw: ImageDraw.ImageDraw,
        img_w: int,
        img_h: int,
        params: Dict[str, Any],
    ) -> None:
        """Fill a semi-transparent rectangle behind the subtitle text."""
        bg_color = params.get("color", "black")
        opacity = int(params.get("opacity", 160))
        padding = int(params.get("padding", 8))
        r, g, b, a = self._parse_color(bg_color, opacity)
        
        draw.rectangle(
            [max(0, -padding), max(0, -padding), img_w + padding, img_h + padding],
            fill=(r, g, b, a),
        )

    def _sanitize_text(self, text: str) -> str:
        """Strip characters that typical CJK fonts cannot render (emoji, symbols)
        to prevent tofu-box glyphs appearing in the output."""
        import unicodedata
        result = []
        for ch in text:
            cp = ord(ch)
            # Drop supplementary-plane code points (U+10000+) – most modern emoji live here
            if cp > 0xFFFF:
                continue
            cat = unicodedata.category(ch)
            # Drop surrogates and private-use area
            if cat in ("Cs", "Co"):
                continue
            # Drop "Symbol, Other" (⊠ ☑ ✅ etc.) unless it's CJK punctuation
            if cat == "So" and not (0x3000 <= cp <= 0x303F or 0x2E80 <= cp <= 0x2EFF):
                continue
            result.append(ch)
        return "".join(result)

    def _get_opencc_converter(self):
        if self._opencc_checked:
            return self._opencc_converter

        self._opencc_checked = True
        try:
            from opencc import OpenCC  # type: ignore
        except Exception:
            self._opencc_converter = None
            return None

        try:
            self._opencc_converter = OpenCC("t2s")
        except Exception:
            self._opencc_converter = None
        return self._opencc_converter

    def _normalize_transcribed_text(self, text: str) -> str:
        normalized = (text or "").strip()
        if not normalized:
            return ""

        converter = self._get_opencc_converter()
        if converter is None:
            return normalized

        try:
            converted = converter.convert(normalized)
        except Exception:
            return normalized
        return converted.strip() or normalized

    def _find_span_range(
        self,
        full_text: str,
        span_text: str,
        covered_cursor: int = 0,
        single_span: bool = False,
    ) -> tuple[int, int]:
        """Locate a span inside the cue text with tolerant normalization fallback."""
        if not full_text or not span_text:
            return (-1, -1)

        def _search(haystack: str, needle: str, start: int) -> int:
            anchor = max(0, min(start, len(haystack)))
            found = haystack.find(needle, anchor)
            if found < 0 and anchor > 0:
                found = haystack.find(needle)
            return found

        start_idx = _search(full_text, span_text, covered_cursor)
        if start_idx >= 0:
            return (start_idx, min(len(full_text), start_idx + len(span_text)))

        normalized_full = self._normalize_transcribed_text(full_text)
        normalized_span = self._normalize_transcribed_text(span_text)
        if normalized_full and normalized_span:
            normalized_idx = _search(normalized_full, normalized_span, covered_cursor)
            if normalized_idx >= 0:
                return (
                    normalized_idx,
                    min(len(full_text), normalized_idx + len(span_text)),
                )

        if single_span:
            return (0, len(full_text))

        return (-1, -1)

    def _wrap_by_pixel_width(self, text: str, font: Any, max_width: int, draw: Any) -> list[str]:
        """Greedy per-character pixel-width wrap.
        Works correctly for CJK (each char ~full-width) and mixed Latin/CJK text."""
        lines: list[str] = []
        current = ""
        for ch in text:
            candidate = current + ch
            # Use textbbox instead of textlength to avoid C-level crashes with certain fonts/characters
            try:
                bbox = draw.textbbox((0, 0), candidate, font=font)
                w = bbox[2] - bbox[0]
            except Exception:
                w = len(candidate) * (getattr(font, 'size', 40) if hasattr(font, 'size') else 40)
            if w <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines or [text]

    def _load_font(self, font_path: Optional[str], font_size: int):
        """Load a font for subtitle rendering.
        
        Priority:
        1. Explicitly specified font_path
        2. Environment variable AICLIP_SUBTITLE_FONT
        3. Bundled fonts in resources/fonts (WenYue preferred)
        4. Windows system fonts (CJK compatible)
        5. Default font
        """
        fonts_dir = Path(__file__).resolve().parents[3] / "resources" / "fonts"
        candidates = []
        configured_font = os.getenv("AICLIP_SUBTITLE_FONT")
        
        # Windows system fonts - fallback for CJK compatibility
        windows_font_candidates = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),      # Microsoft YaHei (微软雅黑)
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),    # Microsoft YaHei Bold
            Path(r"C:\Windows\Fonts\simhei.ttf"),    # SimHei (黑体)
            Path(r"C:\Windows\Fonts\simsun.ttc"),    # SimSun (宋体)
            Path(r"C:\Windows\Fonts\msjh.ttc"),      # Microsoft JhengHei
        ]

        def _append_candidate(path_value: Path) -> None:
            if path_value not in candidates:
                candidates.append(path_value)

        # Priority 1: Explicitly specified font
        if font_path:
            _append_candidate(Path(font_path))
        
        # Priority 2: Environment variable
        if configured_font:
            _append_candidate(Path(configured_font))
        
        # Priority 3: Bundled fonts - WenYue first (now works with Pillow 12+)
        if fonts_dir.exists():
            bundled_candidates = [
                fonts_dir / "WenYue-XinQingNianTi-W8-J-2.otf",  # Preferred
                fonts_dir / "simhei.ttf",
                fonts_dir / "simsun.ttc",
                fonts_dir / "NotoSansCJK-Regular.ttc",
            ]
            for candidate in bundled_candidates:
                if candidate.exists():
                    _append_candidate(candidate)
        
        # Priority 4: Windows system fonts (fallback)
        for candidate in windows_font_candidates:
            if candidate.exists():
                _append_candidate(candidate)

        for candidate in candidates:
            try:
                return ImageFont.truetype(str(candidate), font_size)
            except Exception:
                continue
        
        return ImageFont.load_default()

    def _subtitle_y_position(self, cue: SubtitleCue, image_height: int, video_height: int, project: Optional[Any] = None) -> int:
        position = (cue.position or cue.metadata.get("position") or "bottom").lower()
        margin_top = cue.margin_top
        margin_bottom = cue.margin_bottom

        if margin_top is None and isinstance(cue.metadata.get("margin_top"), (int, float)):
            margin_top = float(cue.metadata["margin_top"])
        if margin_bottom is None and isinstance(cue.metadata.get("margin_bottom"), (int, float)):
            margin_bottom = float(cue.metadata["margin_bottom"])

        top_margin = int(margin_top if margin_top is not None else max(24, int(video_height * 0.06)))
        bottom_margin = int(margin_bottom if margin_bottom is not None else max(24, int(video_height * 0.06)))
        if position == "top":
            y = top_margin
        elif position == "middle":
            y = max(0, (video_height - image_height) // 2)
        elif position == "below_faces" and project and "detected_faces" in project.metadata:
            max_face_y = 0
            for frame in project.metadata["detected_faces"]:
                ts = frame["timestamp"]
                # Check frames near the cue's active time
                if cue.start - 0.5 <= ts <= cue.end + 0.5:
                    for face in frame["faces"]:
                        bottom_edge = face["y"] + face["h"]
                        if bottom_edge > max_face_y:
                            max_face_y = bottom_edge
            if max_face_y > 0:
                y = min(video_height - image_height, max_face_y + 20)
            else:
                y = max(0, video_height - image_height - bottom_margin)
        else:
            y = max(0, video_height - image_height - bottom_margin)

        offset_y = cue.offset_y
        if offset_y == 0 and isinstance(cue.metadata.get("offset_y"), (int, float)):
            offset_y = float(cue.metadata["offset_y"])
        y = int(y + offset_y)
        return max(0, min(y, max(0, video_height - image_height)))

    def _subtitle_x_position(self, cue: SubtitleCue, image_width: int, video_width: int) -> int:
        margin_left = cue.margin_left
        margin_right = cue.margin_right

        if margin_left is None and isinstance(cue.metadata.get("margin_left"), (int, float)):
            margin_left = float(cue.metadata["margin_left"])
        if margin_right is None and isinstance(cue.metadata.get("margin_right"), (int, float)):
            margin_right = float(cue.metadata["margin_right"])

        left_margin = int(margin_left if margin_left is not None else 20)
        right_margin = int(margin_right if margin_right is not None else 20)
        available = max(0, video_width - image_width - left_margin - right_margin)
        if available <= 0:
            return max(0, left_margin)
        return max(0, left_margin + available // 2)

    def _failure(
        self,
        operation: str,
        message: str,
        *,
        code: str,
        path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return ToolResult(
            ok=False,
            status="error",
            code=code,
            message=message,
            operation=operation,
            validation=ValidationSnapshot(passed=False, errors=[message]),
            render_state=RenderState(ready=False, blockers=[code]),
            artifacts=[ArtifactRef(type="project", path=path)] if path else [],
            state={"path": path} if path else {},
            summary=message,
            error=message,
        ).to_dict()

    def _load(self, project_path: str):
        path = Path(project_path)
        if not path.exists():
            return None, self._failure(
                "load_project",
                f"Project file not found: {project_path}",
                code="project.not_found",
                path=str(path),
            )
        try:
            return self.store.load(path), None
        except Exception as exc:
            return None, self._failure(
                "load_project",
                f"Failed to load project: {exc}",
                code="project.load_failed",
                path=str(path),
            )

    def _probe_media(self, media_path: Path) -> Dict[str, Any]:
        clip = None
        is_audio_only = media_path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
        try:
            if is_audio_only:
                clip = AudioFileClip(str(media_path))
                return {
                    "duration": float(clip.duration or 0.0),
                    "fps": 0.0,
                    "size": [0, 0],
                    "has_audio": True,
                    "media_kind": "audio",
                }

            clip = VideoFileClip(str(media_path))
            return {
                "duration": float(clip.duration or 0.0),
                "fps": float(getattr(clip, "fps", 0.0) or 0.0),
                "size": [int(clip.w), int(clip.h)],
                "has_audio": clip.audio is not None,
                "media_kind": "video",
            }
        finally:
            if clip is not None:
                clip.close()

    def create_project_from_media(
        self,
        media_path: str,
        project_path: Optional[str] = None,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        track_id: str = "video_1",
        clip_id: str = "clip_1",
    ) -> Dict[str, Any]:
        source_path = Path(media_path).resolve()
        if not source_path.exists():
            return self._failure(
                "create_project_from_media",
                f"Media file not found: {media_path}",
                code="media.not_found",
                path=str(source_path),
            )

        if project_path is None:
            existing_project_path = self.store.find_project_for_media(source_path)
            if existing_project_path is not None and existing_project_path.exists():
                existing_project = self.store.load(existing_project_path)
                report = self.store.validate(existing_project)
                return ToolResult(
                    ok=report.passed,
                    status="ok" if report.passed else "warn",
                    code="project.reused",
                    message="Existing project loaded for media path",
                    operation="create_project_from_media",
                    project_id=existing_project.id,
                    project_version=existing_project.version,
                    validation=ValidationSnapshot(
                        passed=report.passed,
                        warnings=[issue.message for issue in report.warnings],
                        errors=[issue.message for issue in report.errors],
                    ),
                    render_state=RenderState(
                        ready=report.passed,
                        blockers=[issue.code for issue in report.errors],
                    ),
                    artifacts=[ArtifactRef(type="project", path=str(existing_project_path)), ArtifactRef(type="media", path=str(source_path))],
                    state={
                        "project_path": str(existing_project_path),
                        "media_path": str(source_path),
                        "reused_existing_project": True,
                        **self._project_counts(existing_project),
                    },
                    payload=existing_project.to_dict(),
                    summary=f"Reused existing project {existing_project.name}",
                ).to_dict()

        try:
            media_info = self._probe_media(source_path)
        except Exception as exc:
            return self._failure(
                "create_project_from_media",
                f"Failed to inspect media: {exc}",
                code="media.inspect_failed",
                path=str(source_path),
            )

        asset = Asset(
            id=asset_id or source_path.stem,
            path=str(source_path),
            source="local",
            media_type=media_info.get("media_kind", "video"),
            duration=media_info["duration"] or None,
            metadata={
                "source_media_path": str(source_path),
                "has_audio": media_info["has_audio"],
                "fps": media_info["fps"],
                "size": media_info["size"],
                "media_kind": media_info.get("media_kind", "video"),
            },
        )

        clip_duration = media_info["duration"] if media_info["duration"] > 0 else 0.0
        track_kind = media_info.get("media_kind", "video")
        tracks = [
            Track(
                id=track_id,
                kind=track_kind,
                name="Main Audio" if track_kind == "audio" else "Main Video",
                clips=[
                    Clip(
                        id=clip_id,
                        asset_id=asset.id,
                        start=0.0,
                        end=clip_duration,
                        source_in=0.0,
                        source_out=clip_duration,
                    )
                ],
            )
        ]

        if track_kind == "video" and media_info["has_audio"]:
            tracks.append(
                Track(
                    id="audio_1",
                    kind="audio",
                    name="Main Audio",
                    role="dialogue",
                    volume=1.0,
                    clips=[
                        Clip(
                            id=f"{clip_id}_audio",
                            asset_id=asset.id,
                            start=0.0,
                            end=clip_duration,
                            source_in=0.0,
                            source_out=clip_duration,
                        )
                    ],
                )
            )

        timeline = Timeline(
            duration=clip_duration,
            fps=media_info["fps"] or None,
            tracks=tracks,
        )

        project = Project(
            id=project_id or source_path.stem,
            name=project_name or source_path.stem,
            assets=[asset],
            timeline=timeline,
            metadata={
                "source_media_path": str(source_path),
                "source_media_name": source_path.name,
                "source_media_duration": media_info["duration"],
                "source_media_fps": media_info["fps"],
                "source_media_has_audio": media_info["has_audio"],
                "source_media_kind": media_info.get("media_kind", "video"),
                "subtitle_source_present": False,
                "analysis_scope": "project_core",
            },
        )

        report = self.store.validate(project)
        if project_path:
            target_path = Path(project_path).resolve()
        else:
            target_path, _ = self.store.find_or_create_project_for_media(source_path, project_name=project_name or source_path.stem)

        project.metadata["project_path"] = str(target_path)
        try:
            saved_path = self.store.save(project, target_path)
            self.store.register_media_project(source_path, saved_path)
        except Exception as exc:
            return self._failure(
                "create_project_from_media",
                f"Failed to save project: {exc}",
                code="project.save_failed",
                path=str(target_path),
            )

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.created",
            message="Project created from media",
            operation="create_project_from_media",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed,
                blockers=[issue.code for issue in report.errors],
            ),
            artifacts=[ArtifactRef(type="project", path=str(saved_path)), ArtifactRef(type="media", path=str(source_path))],
            state={
                "project_path": str(saved_path),
                "media_path": str(source_path),
                "subtitle_source_present": False,
                "audio_track_present": media_info["has_audio"],
                **self._project_counts(project),
            },
            payload=project.to_dict(),
            summary=f"Created project for {source_path.name}",
        ).to_dict()

    def load_project(self, project_path: str) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.loaded",
            message="Project loaded",
            operation="load_project",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed,
                blockers=[issue.code for issue in report.errors],
            ),
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "subtitle_source_present": bool(project.subtitles),
                "audio_track_present": any(item.kind == "audio" and item.clips for item in project.timeline.tracks),
                **self._project_counts(project),
            },
            payload=project.to_dict(),
            summary=f"Loaded project {project.name}",
        ).to_dict()

    def get_project_summary(self, project_path: str) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        report = self.store.validate(project)
        payload = self._project_summary_payload(project, project_path)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.summary.ready",
            message="Project summary ready",
            operation="get_project_summary",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "timeline_duration": payload["timeline_duration"],
                **self._project_counts(project),
            },
            payload=payload,
            summary=f"Prepared summary for project {project.name}",
        ).to_dict()

    def search_project_subtitles(
        self,
        project_path: str,
        query: str = "",
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        normalized_query = query.casefold().strip()
        normalized_speaker = speaker.casefold().strip() if isinstance(speaker, str) and speaker.strip() else None
        normalized_language = language.casefold().strip() if isinstance(language, str) and language.strip() else None

        matches = []
        for cue in sorted(project.subtitles, key=lambda item: (item.start, item.end, item.id)):
            if normalized_query and normalized_query not in cue.text.casefold():
                continue
            if normalized_speaker and (cue.speaker or "").casefold() != normalized_speaker:
                continue
            if normalized_language and (cue.language or "").casefold() != normalized_language:
                continue
            matches.append(self._subtitle_search_entry(cue))
            if len(matches) >= max(1, int(limit)):
                break

        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.search.completed",
            message="Subtitle search completed",
            operation="search_project_subtitles",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "query": query,
                "speaker": speaker,
                "language": language,
                "match_count": len(matches),
                "subtitle_source_present": bool(project.subtitles),
            },
            payload={
                "project_path": str(Path(project_path)),
                "query": query,
                "speaker": speaker,
                "language": language,
                "matches": matches,
            },
            summary=f"Found {len(matches)} subtitle matches",
        ).to_dict()

    def list_project_clips(
        self,
        project_path: str,
        track_id: Optional[str] = None,
        track_kind: Optional[str] = None,
        asset_id: Optional[str] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        normalized_track_kind = track_kind.casefold().strip() if isinstance(track_kind, str) and track_kind.strip() else None
        normalized_asset_id = asset_id.strip() if isinstance(asset_id, str) and asset_id.strip() else None
        matches = []
        for track in project.timeline.tracks:
            if track_id and track.id != track_id:
                continue
            if normalized_track_kind and track.kind.casefold() != normalized_track_kind:
                continue

            for clip in sorted(track.clips, key=lambda item: (item.start, item.end, item.id)):
                duration = float(clip.end - clip.start)
                if normalized_asset_id and clip.asset_id != normalized_asset_id:
                    continue
                if min_duration is not None and duration < float(min_duration):
                    continue
                if max_duration is not None and duration > float(max_duration):
                    continue
                matches.append(self._clip_listing_entry(project, track, clip))
                if len(matches) >= max(1, int(limit)):
                    break
            if len(matches) >= max(1, int(limit)):
                break

        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="clip.list.completed",
            message="Clip list ready",
            operation="list_project_clips",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "track_id": track_id,
                "track_kind": track_kind,
                "asset_id": asset_id,
                "match_count": len(matches),
            },
            payload={
                "project_path": str(Path(project_path)),
                "filters": {
                    "track_id": track_id,
                    "track_kind": track_kind,
                    "asset_id": asset_id,
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                },
                "clips": matches,
            },
            summary=f"Found {len(matches)} clips",
        ).to_dict()

    def save_project(
        self,
        project_path: str,
        output_path: Optional[str] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        target_path = Path(output_path or project_path)
        try:
            saved_path = self.store.save(project, target_path, format=format)  # type: ignore[arg-type]
        except Exception as exc:
            return self._failure(
                "save_project",
                f"Failed to save project: {exc}",
                code="project.save_failed",
                path=str(target_path),
            )

        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.saved",
            message="Project saved",
            operation="save_project",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={"project_path": str(saved_path), "format": format or saved_path.suffix.lstrip(".")},
            payload=project.to_dict(),
            summary=f"Saved project to {saved_path}",
        ).to_dict()

    def trim_project_clip(
        self,
        project_path: str,
        clip_id: str,
        start: float,
        end: float,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = TrimClipCommand(clip_id=clip_id, start=start, end=end, track_id=track_id)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="trim_project_clip",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="clip.trimmed",
            message="Clip trimmed",
            operation="trim_project_clip",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed,
                blockers=[issue.code for issue in report.errors],
            ),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            next_actions=["save_project"] if not report.passed else [],
            summary=f"Trimmed clip {clip_id}",
        ).to_dict()

    def set_project_clip_speed(
        self,
        project_path: str,
        clip_id: str,
        speed: float,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = SetClipSpeedCommand(clip_id=clip_id, speed=speed, track_id=track_id)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="set_project_clip_speed",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="clip.speed.updated",
            message="Clip speed updated",
            operation="set_project_clip_speed",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated speed for clip {clip_id}",
        ).to_dict()

    def add_project_asset(
        self,
        project_path: str,
        asset_id: str,
        asset_path: str,
        media_type: str = "unknown",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = AddAssetCommand(
            Asset(
                id=asset_id,
                path=asset_path,
                source="local" if Path(asset_path).is_absolute() else "net_asset",
                media_type=media_type,
            )
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_asset",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="asset.added",
            message="Asset added",
            operation="add_project_asset",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added asset {asset_id}",
        ).to_dict()

    def add_project_clip(
        self,
        project_path: str,
        clip_id: str,
        asset_id: str,
        start: float,
        end: float,
        track_id: str,
        source_in: float = 0.0,
        source_out: Optional[float] = None,
        speed: float = 1.0,
        track_kind: str = "video",
        track_name: str = "",
        transform: Optional[Dict[str, Any]] = None,
        insert_index: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = AddClipCommand(
            clip=Clip(
                id=clip_id,
                asset_id=asset_id,
                start=float(start),
                end=float(end),
                source_in=float(source_in),
                source_out=float(source_out) if source_out is not None else None,
                speed=float(speed),
                transform=dict(transform or {}),
            ),
            track_id=track_id,
            track_kind=track_kind,
            track_name=track_name,
            insert_index=insert_index,
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_clip",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="clip.added",
            message="Clip added to timeline",
            operation="add_project_clip",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "clip_id": clip_id, "asset_id": asset_id},
            payload=project.to_dict(),
            summary=f"Added clip {clip_id} to track {track_id}",
        ).to_dict()

    def add_project_subtitle(
        self,
        project_path: str,
        subtitle_id: str,
        start: float,
        end: float,
        text: str,
        spans: Optional[Any] = None,
        track_id: Optional[str] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        position: Optional[str] = None,
        margin_top: Optional[float] = None,
        margin_bottom: Optional[float] = None,
        margin_left: Optional[float] = None,
        margin_right: Optional[float] = None,
        offset_y: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if spans is not None:
            try:
                spans = self._coerce_json_array(spans, "spans")
            except (json.JSONDecodeError, ValueError) as exc:
                return self._failure(
                    "add_project_subtitle",
                    f"Invalid spans: {exc}",
                    code="subtitle.invalid_spans",
                    path=str(Path(project_path)),
                )

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            command = AddSubtitleCueCommand(
                SubtitleCue(
                    id=subtitle_id,
                    start=start,
                    end=end,
                    text=self._normalize_transcribed_text(text),
                    spans=self._normalize_subtitle_spans(subtitle_id, spans or []),
                    track_id=track_id,
                    speaker=speaker,
                    language=language,
                    position=position,
                    margin_top=margin_top,
                    margin_bottom=margin_bottom,
                    margin_left=margin_left,
                    margin_right=margin_right,
                    offset_y=offset_y or 0.0,
                )
            )
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="add_project_subtitle",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.added",
            message="Subtitle cue added",
            operation="add_project_subtitle",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added subtitle cue {subtitle_id}",
        ).to_dict()

    def update_project_subtitle(
        self,
        project_path: str,
        subtitle_id: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
        text: Optional[str] = None,
        spans: Optional[Any] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        position: Optional[str] = None,
        margin_top: Optional[float] = None,
        margin_bottom: Optional[float] = None,
        margin_left: Optional[float] = None,
        margin_right: Optional[float] = None,
        offset_y: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        normalized_spans = None
        if spans is not None:
            try:
                normalized_spans = self._coerce_json_array(spans, "spans")
            except (json.JSONDecodeError, ValueError) as exc:
                return self._failure(
                    "update_project_subtitle",
                    f"Invalid spans: {exc}",
                    code="subtitle.invalid_spans",
                    path=str(Path(project_path)),
                )

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure
            command = UpdateSubtitleCueCommand(
                cue_id=subtitle_id,
                start=start,
                end=end,
                text=self._normalize_transcribed_text(text) if text is not None else None,
                spans=self._normalize_subtitle_spans(
                    subtitle_id,
                    normalized_spans,
                ) if normalized_spans is not None else None,
                speaker=speaker,
                language=language,
                position=position,
                margin_top=margin_top,
                margin_bottom=margin_bottom,
                margin_left=margin_left,
                margin_right=margin_right,
                offset_y=offset_y,
            )
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="update_project_subtitle",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.updated",
            message="Subtitle cue updated",
            operation="update_project_subtitle",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated subtitle cue {subtitle_id}",
        ).to_dict()

    def remove_project_subtitle(
        self,
        project_path: str,
        subtitle_id: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            command = RemoveSubtitleCueCommand(subtitle_id)
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="remove_project_subtitle",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.removed",
            message="Subtitle cue removed",
            operation="remove_project_subtitle",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Removed subtitle cue {subtitle_id}",
        ).to_dict()

    def add_project_subtitle_span(
        self,
        project_path: str,
        subtitle_id: str,
        text: str,
        span_id: Optional[str] = None,
        color: Optional[str] = None,
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        index: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            cue = next((item for item in project.subtitles if item.id == subtitle_id), None)
            if cue is None:
                return self._failure(
                    "add_project_subtitle_span",
                    f"Subtitle cue not found: {subtitle_id}",
                    code="subtitle.not_found",
                    path=str(Path(project_path)),
                )

            span = SubtitleSpan(
                id=span_id or "",
                text=text,
                color=color,
                bold=bold,
                italic=italic,
                underline=underline,
            )
            command = AddSubtitleSpanCommand(subtitle_id, span, index=index)
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="add_project_subtitle_span",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle_span.added",
            message="Subtitle span added",
            operation="add_project_subtitle_span",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "subtitle_id": subtitle_id},
            payload=project.to_dict(),
            summary=f"Added subtitle span {result.changes[0].id if result.changes else span.id}",
        ).to_dict()

    def update_project_subtitle_span(
        self,
        project_path: str,
        subtitle_id: str,
        span_id: str,
        text: Optional[str] = None,
        color: Optional[str] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure
            command = UpdateSubtitleSpanCommand(
                cue_id=subtitle_id,
                span_id=span_id,
                text=text,
                color=color,
                bold=bold,
                italic=italic,
                underline=underline,
            )
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="update_project_subtitle_span",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle_span.updated",
            message="Subtitle span updated",
            operation="update_project_subtitle_span",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "subtitle_id": subtitle_id, "span_id": span_id},
            payload=project.to_dict(),
            summary=f"Updated subtitle span {span_id}",
        ).to_dict()

    def remove_project_subtitle_span(
        self,
        project_path: str,
        subtitle_id: str,
        span_id: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            command = RemoveSubtitleSpanCommand(subtitle_id, span_id)
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="remove_project_subtitle_span",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle_span.removed",
            message="Subtitle span removed",
            operation="remove_project_subtitle_span",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "subtitle_id": subtitle_id, "span_id": span_id},
            payload=project.to_dict(),
            summary=f"Removed subtitle span {span_id}",
        ).to_dict()

    # ------------------------------------------------------------------
    # Subtitle effect tools
    # ------------------------------------------------------------------

    def set_project_subtitle_effect(
        self,
        project_path: str,
        subtitle_id: str,
        kind: str,
        parameters: Optional[Any] = None,
        replace: bool = True,
        output_path: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach a visual or animation effect to a subtitle cue.

        Supported *kind* values
        -----------------------
        Visual (applied to the still subtitle image):
          ``outline``        – text stroke; params: color, width (default 2)
          ``glow``           – luminous halo; params: color (default "white"), radius (default 4)
          ``background_box`` – filled rect behind text; params: color (default "black"), opacity (default 160), padding (default 8)
          ``gradient``       – gradient text fill; params: color_top, color_bottom, direction ("vertical"|"horizontal")

        Animation (applied during render):
          ``fade_in``    – opacity ramp in; params: duration (default 0.3 s)
          ``fade_out``   – opacity ramp out; params: duration (default 0.3 s)
          ``slide_in``   – slide on entry; params: direction ("bottom"|"top"|"left"|"right"), duration, distance (px)
          ``slide_out``  – slide on exit; params: direction, duration, distance
          ``typewriter`` – reveal characters; params: chars_per_second (default 20)
          ``scale_in``   – zoom in; params: duration (default 0.3 s)
        """
        project, failure = self._load(project_path)
        if failure:
            return failure

        try:
            normalized_parameters = self._coerce_json_object(parameters, "parameters")
        except (json.JSONDecodeError, ValueError) as exc:
            return self._failure(
                "set_project_subtitle_effect",
                f"Invalid parameters: {exc}",
                code="subtitle.effect.invalid_parameters",
                path=str(Path(project_path)),
            )

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            command = SetSubtitleEffectCommand(
                cue_id=subtitle_id,
                kind=kind,
                parameters=normalized_parameters,
                replace=replace,
                span_id=span_id,
            )
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="set_project_subtitle_effect",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.effect.set",
            message=f"Effect '{kind}' applied to subtitle {subtitle_id}",
            operation="set_project_subtitle_effect",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "subtitle_id": subtitle_id, "effect_kind": kind},
            payload=project.to_dict(),
            summary=f"Applied subtitle effect '{kind}' to cue {subtitle_id}",
        ).to_dict()

    def remove_project_subtitle_effect(
        self,
        project_path: str,
        subtitle_id: str,
        kind: Optional[str] = None,
        output_path: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove one or all effects from a subtitle cue.

        Pass *kind* to remove only effects of that type, or omit it to clear all effects.
        """
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            command = RemoveSubtitleEffectCommand(cue_id=subtitle_id, kind=kind, span_id=span_id)
            result = command.execute(project)
            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="remove_project_subtitle_effect",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.effect.removed",
            message=f"Effect(s) removed from subtitle {subtitle_id}",
            operation="remove_project_subtitle_effect",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path), "subtitle_id": subtitle_id},
            payload=project.to_dict(),
            summary=f"Removed subtitle effect(s) from cue {subtitle_id}",
        ).to_dict()

    def batch_update_project_subtitles(
        self,
        project_path: str,
        entries: Any,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply subtitle styling updates for many cues in one tool call.

        Each entry accepts:
          - subtitle_id (required)
          - start, end, text, speaker, language
          - position, margin_top, margin_bottom, margin_left, margin_right, offset_y
          - spans: list of subtitle span objects
          - effects: list of {kind, parameters, replace?, span_id?}
        """
        try:
            normalized_entries = self._coerce_subtitle_style_entries(entries)
        except (json.JSONDecodeError, ValueError) as exc:
            return self._failure(
                "batch_update_project_subtitles",
                f"Invalid entries: {exc}",
                code="subtitle.batch.invalid_entries",
                path=str(Path(project_path)),
            )

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            updated_ids: list[str] = []
            applied_effect_count = 0

            for entry in normalized_entries:
                subtitle_id = str(entry["subtitle_id"])
                spans = entry.get("spans")
                command = UpdateSubtitleCueCommand(
                    cue_id=subtitle_id,
                    start=entry.get("start"),
                    end=entry.get("end"),
                    text=self._normalize_transcribed_text(entry["text"]) if entry.get("text") is not None else None,
                    spans=self._normalize_subtitle_spans(
                        subtitle_id,
                        spans,
                    ) if spans is not None else None,
                    speaker=entry.get("speaker"),
                    language=entry.get("language"),
                    position=entry.get("position"),
                    margin_top=entry.get("margin_top"),
                    margin_bottom=entry.get("margin_bottom"),
                    margin_left=entry.get("margin_left"),
                    margin_right=entry.get("margin_right"),
                    offset_y=entry.get("offset_y"),
                )
                result = command.execute(project)
                if not result.ok:
                    return ToolResult(
                        ok=False,
                        status="error",
                        code=result.code,
                        message=result.message,
                        operation="batch_update_project_subtitles",
                        project_id=project.id,
                        project_version=project.version,
                        validation=result.validation,
                        render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                        state={"project_path": str(Path(project_path)), "subtitle_id": subtitle_id},
                        summary=result.message,
                        error=result.message,
                    ).to_dict()

                for effect in entry.get("effects") or []:
                    effect_command = SetSubtitleEffectCommand(
                        cue_id=subtitle_id,
                        kind=str(effect["kind"]),
                        parameters=dict(effect.get("parameters") or {}),
                        replace=bool(effect.get("replace", True)),
                        span_id=effect.get("span_id"),
                    )
                    effect_result = effect_command.execute(project)
                    if not effect_result.ok:
                        return ToolResult(
                            ok=False,
                            status="error",
                            code=effect_result.code,
                            message=effect_result.message,
                            operation="batch_update_project_subtitles",
                            project_id=project.id,
                            project_version=project.version,
                            validation=effect_result.validation,
                            render_state=RenderState(ready=False, blockers=list(effect_result.validation.errors)),
                            state={
                                "project_path": str(Path(project_path)),
                                "subtitle_id": subtitle_id,
                                "effect_kind": effect.get("kind"),
                            },
                            summary=effect_result.message,
                            error=effect_result.message,
                        ).to_dict()
                    applied_effect_count += 1

                updated_ids.append(subtitle_id)

            saved_path = self.store.save(project, output_path or project_path, _already_locked=True)
            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.batch.updated",
            message="Subtitle styling batch applied",
            operation="batch_update_project_subtitles",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={
                "project_path": str(saved_path),
                "updated_subtitle_ids": updated_ids,
                "updated_subtitle_count": len(updated_ids),
                "applied_effect_count": applied_effect_count,
            },
            summary=f"Applied styling to {len(updated_ids)} subtitles with {applied_effect_count} effect updates",
        ).to_dict()

    def transcribe_audio(
        self,
        project_path: str,
        language: Optional[str] = None,
        audio_path: Optional[str] = None,
        model_size: str = "tiny",
        output_path: Optional[str] = None,
        replace_existing: bool = True,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        source_path = self._resolve_media_path(project, audio_path, project_path)
        if source_path is None:
            return self._failure(
                "transcribe_audio",
                "No media source available for transcription",
                code="media.source.missing",
                path=str(Path(project_path)),
            )

        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            segments_iter, info = model.transcribe(str(source_path), language=language, vad_filter=True)
            cues: list[SubtitleCue] = []
            for index, segment in enumerate(segments_iter, start=1):
                text = self._normalize_transcribed_text(segment.text or "")
                if not text:
                    continue
                cues.append(
                SubtitleCue(
                    id=f"sub_{index:04d}",
                    start=float(segment.start),
                    end=float(segment.end),
                    text=text,
                    language=language or getattr(info, "language", None),
                    position="bottom",
                    margin_bottom=0.0,
                    offset_y=0.0,
                    metadata={
                        "source": "transcribe_audio",
                        "segment_index": index,
                    },
                )
                )
        except Exception as exc:
            return self._failure(
                "transcribe_audio",
                f"Failed to transcribe audio: {exc}",
                code="transcription.failed",
                path=str(source_path),
            )

        if replace_existing:
            project.subtitles = cues
        else:
            project.subtitles.extend(cues)
        project.metadata["subtitle_source_present"] = bool(project.subtitles)
        if language or getattr(info, "language", None):
            project.metadata["subtitle_language"] = language or getattr(info, "language", None)
        project.bump_version()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.transcribed",
            message="Audio transcribed to project subtitles",
            operation="transcribe_audio",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path)), ArtifactRef(type="media", path=str(source_path))],
            state={
                "project_path": str(saved_path),
                "media_path": str(source_path),
                "subtitle_source_present": bool(project.subtitles),
                "subtitle_count": len(project.subtitles),
                "subtitle_text_normalized": self._get_opencc_converter() is not None,
            },
            payload=project.to_dict(),
            next_actions=["remove_project_silence", "prepare_project_render"],
            summary=f"Transcribed {len(cues)} subtitle cues",
        ).to_dict()

    def remove_project_silence(
        self,
        project_path: str,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
        padding: float = 0.0,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        if not project.subtitles:
            return ToolResult(
                ok=False,
                status="error",
                code="subtitle.source.missing",
                message="No subtitle source available for silence removal",
                operation="remove_project_silence",
                project_id=project.id,
                project_version=project.version,
                validation=ValidationSnapshot(passed=False, errors=["No subtitle cues available"]),
                render_state=RenderState(ready=False, blockers=["subtitle.source.missing"]),
                state={"project_path": str(Path(project_path)), "subtitle_source_present": False},
                summary="No subtitle cues available",
                error="No subtitle cues available",
            ).to_dict()

        track = self._project_main_track(project, track_id)
        if track is None or not track.clips:
            return self._failure(
                "remove_project_silence",
                "No timeline track available for silence removal",
                code="timeline.track.missing",
                path=str(Path(project_path)),
            )

        source_duration = self._project_source_duration(project, project_path)
        if source_duration is None:
            source_duration = max((float(item.end) for track_item in project.timeline.tracks for item in track_item.clips), default=0.0)

        speech_intervals = self._merge_intervals(
            [
                (
                    max(0.0, min(float(cue.start - padding), source_duration)),
                    max(
                        max(0.0, min(float(cue.end + padding), source_duration)),
                        max(0.0, min(float(cue.start), source_duration)),
                    ),
                )
                for cue in sorted(project.subtitles, key=lambda item: (item.start, item.end))
            ]
        )
        if not speech_intervals:
            return self._failure(
                "remove_project_silence",
                "No usable speech intervals were found in subtitles",
                code="subtitle.intervals.missing",
                path=str(Path(project_path)),
            )

        rebuild_tracks = [item for item in project.timeline.tracks if item.kind in {"video", "audio"} and item.clips]
        if not rebuild_tracks:
            rebuild_tracks = [track]

        new_clips_by_track: dict[str, list[Clip]] = {}
        remapped_subtitles: list[SubtitleCue] = []
        output_cursor = 0.0
        for rebuild_track in rebuild_tracks:
            source_clip = rebuild_track.clips[0]
            rebuilt_clips: list[Clip] = []
            track_cursor = 0.0
            for index, (start, end) in enumerate(speech_intervals, start=1):
                segment_duration = max(0.0, end - start)
                if segment_duration <= 0:
                    continue
                rebuilt_clips.append(
                    Clip(
                        id=f"{source_clip.id}_{rebuild_track.id}_seg_{index:03d}",
                        asset_id=source_clip.asset_id,
                        start=track_cursor,
                        end=track_cursor + segment_duration,
                        source_in=start,
                        source_out=end,
                        speed=source_clip.speed,
                        transform=dict(source_clip.transform),
                        metadata={**dict(source_clip.metadata), "source_segment_index": index, "track_id": rebuild_track.id},
                    )
                )
                track_cursor += segment_duration

            new_clips_by_track[rebuild_track.id] = rebuilt_clips
            output_cursor = max(output_cursor, track_cursor)

        for cue in sorted(project.subtitles, key=lambda item: (item.start, item.end)):
            new_start = self._remap_time(cue.start, speech_intervals)
            new_end = self._remap_time(cue.end, speech_intervals)
            if new_end <= new_start:
                continue
            remapped_subtitles.append(
                SubtitleCue(
                    id=cue.id,
                    start=new_start,
                    end=new_end,
                    text=cue.text,
                    spans=[SubtitleSpan.from_dict(span.to_dict() if hasattr(span, "to_dict") else dict(span)) if isinstance(span, dict) else SubtitleSpan.from_dict(span.__dict__) if hasattr(span, "__dict__") else span for span in cue.spans],
                    effects=[SubtitleEffect.from_dict(effect.to_dict() if hasattr(effect, "to_dict") else dict(effect)) if isinstance(effect, dict) else SubtitleEffect.from_dict(effect.__dict__) if hasattr(effect, "__dict__") else effect for effect in cue.effects],
                    track_id=cue.track_id,
                    speaker=cue.speaker,
                    language=cue.language,
                    position=cue.position,
                    margin_top=cue.margin_top,
                    margin_bottom=cue.margin_bottom,
                    margin_left=cue.margin_left,
                    margin_right=cue.margin_right,
                    offset_y=cue.offset_y,
                    font_size=cue.font_size,
                    font_path=cue.font_path,
                    metadata=dict(cue.metadata),
                )
            )

        for rebuild_track in rebuild_tracks:
            rebuild_track.clips = new_clips_by_track.get(rebuild_track.id, [])
        project.subtitles = remapped_subtitles
        project.timeline.duration = output_cursor
        project.metadata["subtitle_source_present"] = bool(project.subtitles)
        project.metadata["audio_track_present"] = any(item.kind == "audio" and item.clips for item in project.timeline.tracks)
        project.bump_version()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="timeline.silence.removed",
            message="Silence removed from timeline",
            operation="remove_project_silence",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={
                "project_path": str(saved_path),
                "track_id": track.id,
                "subtitle_source_present": bool(project.subtitles),
                "audio_track_present": any(item.kind == "audio" and item.clips for item in project.timeline.tracks),
                "subtitle_count": len(project.subtitles),
                "segment_count": len(next(iter(new_clips_by_track.values()), [])),
                "timeline_duration": output_cursor,
            },
            payload=project.to_dict(),
            next_actions=["prepare_project_render"],
            summary=f"Removed silence with {len(next(iter(new_clips_by_track.values()), []))} retained segments",
        ).to_dict()

    def detect_faces(
        self,
        project_path: str,
        media_path: Optional[str] = None,
        timestamps: Optional[List[float]] = None,
        sample_interval: float = 1.0,
        max_frames: int = 30,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_face_size: int = 30,
    ) -> Dict[str, Any]:
        try:
            import cv2
        except ImportError:
            return self._failure(
                "detect_faces",
                "opencv-python is required. Run: pip install opencv-python",
                code="dependency.missing",
            )

        project, failure = self._load(project_path)
        if failure:
            return failure

        source_path = self._resolve_media_path(project, media_path, project_path)
        if source_path is None:
            return self._failure(
                "detect_faces",
                "No media source found in project",
                code="media.source.missing",
                path=str(Path(project_path)),
            )

        cap = cv2.VideoCapture(str(source_path))
        if not cap.isOpened():
            return self._failure(
                "detect_faces",
                f"Cannot open video: {source_path}",
                code="media.open_failed",
                path=str(source_path),
            )

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0.0
            video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if timestamps:
                sample_times = [float(t) for t in timestamps if 0.0 <= float(t) <= duration]
            else:
                if sample_interval <= 0:
                    sample_interval = 1.0
                sample_times = []
                t = 0.0
                while t <= duration and len(sample_times) < max_frames:
                    sample_times.append(t)
                    t += sample_interval

            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            detector = cv2.CascadeClassifier(cascade_path)

            frame_results: List[Dict[str, Any]] = []
            total_faces = 0

            for ts in sample_times:
                frame_index = int(ts * fps)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                if not ret:
                    continue

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(
                    gray,
                    scaleFactor=scale_factor,
                    minNeighbors=min_neighbors,
                    minSize=(min_face_size, min_face_size),
                )

                face_list: List[Dict[str, Any]] = []
                for x, y, w, h in (faces if len(faces) > 0 else []):
                    face_list.append({
                        "x": int(x),
                        "y": int(y),
                        "w": int(w),
                        "h": int(h),
                        "cx": int(x + w // 2),
                        "cy": int(y + h // 2),
                        "norm_x": round(x / video_width, 4) if video_width else 0,
                        "norm_y": round(y / video_height, 4) if video_height else 0,
                        "norm_w": round(w / video_width, 4) if video_width else 0,
                        "norm_h": round(h / video_height, 4) if video_height else 0,
                    })

                total_faces += len(face_list)
                frame_results.append({
                    "timestamp": round(ts, 3),
                    "frame_index": frame_index,
                    "face_count": len(face_list),
                    "faces": face_list,
                })
        finally:
            cap.release()

        frames_with_faces = sum(1 for f in frame_results if f["face_count"] > 0)
        project.metadata["detected_faces"] = frame_results
        saved_path = self.store.save(project, project_path)

        return ToolResult(
            ok=True,
            status="ok",
            code="faces.detected",
            message=f"Detected {total_faces} face(s) across {len(frame_results)} sampled frame(s)",
            operation="detect_faces",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(passed=True),
            render_state=RenderState(ready=True, blockers=[]),
            artifacts=[ArtifactRef(type="media", path=str(source_path)), ArtifactRef(type="project", path=str(saved_path))],
            state={
                "media_path": str(source_path),
                "project_path": str(saved_path),
                "video_width": video_width,
                "video_height": video_height,
                "duration": round(duration, 3),
                "fps": round(fps, 3),
                "frames_sampled": len(frame_results),
                "frames_with_faces": frames_with_faces,
                "total_faces_detected": total_faces,
            },
            payload={
                "video_width": video_width,
                "video_height": video_height,
                "duration": round(duration, 3),
                "fps": round(fps, 3),
                "frames": frame_results,
                "total_faces_detected": total_faces,
                "frames_with_faces": frames_with_faces,
            },
            summary=f"Found faces in {frames_with_faces}/{len(frame_results)} frames, {total_faces} total detections",
        ).to_dict()

    # ------------------------------------------------------------------
    # Subtitle animation helpers (used by render_project)
    # ------------------------------------------------------------------

    def _apply_slide_anim(
        self,
        clip: Any,
        params: Dict[str, Any],
        x_pos: int,
        y_pos: int,
        anchor_time: float,
        mode: str,
    ) -> Any:
        """Return clip with a slide-in or slide-out position lambda."""
        direction = str(params.get("direction", "bottom")).lower()
        duration = float(params.get("duration", 0.3))
        distance = int(params.get("distance", 40))

        def _pos(t: float) -> tuple[int, int]:
            if mode == "in":
                progress = min(1.0, max(0.0, (t - anchor_time) / duration)) if duration > 0 else 1.0
            else:
                progress = min(1.0, max(0.0, (t - (anchor_time - duration)) / duration)) if duration > 0 else 1.0
            ease = progress * progress * (3 - 2 * progress)  # smoothstep
            slide = int(distance * (1.0 - ease)) if mode == "in" else int(distance * ease)
            if direction == "bottom":
                return (x_pos, y_pos + slide)
            elif direction == "top":
                return (x_pos, y_pos - slide)
            elif direction == "left":
                return (x_pos - slide, y_pos)
            elif direction == "right":
                return (x_pos + slide, y_pos)
            return (x_pos, y_pos)

        try:
            return self._clip_call(clip, "with_position", _pos)
        except Exception:
            return self._clip_call(clip, "with_position", (x_pos, y_pos))

    def _apply_scale_in(self, clip: Any, params: Dict[str, Any], x_pos: int, y_pos: int) -> Any:
        """Return clip with a scale-from-zero effect via resize lambda."""
        duration = float(params.get("duration", 0.3))
        base_w, base_h = getattr(clip, "size", (0, 0))

        def _progress(t: float) -> float:
            progress = min(1.0, max(0.0, t / duration)) if duration > 0 else 1.0
            return progress * progress * (3 - 2 * progress)

        def _scale(t: float) -> tuple[int, int]:
            ease = _progress(t)
            width = max(1, int(round(base_w * max(0.01, ease))))
            height = max(1, int(round(base_h * max(0.01, ease))))
            return (width, height)

        def _position(t: float) -> tuple[int, int]:
            ease = _progress(t)
            width = max(1, int(round(base_w * max(0.01, ease))))
            height = max(1, int(round(base_h * max(0.01, ease))))
            return (
                x_pos + max(0, (base_w - width) // 2),
                y_pos + max(0, (base_h - height) // 2),
            )

        try:
            clip = self._clip_call(clip, "resized", _scale)
            return self._clip_call(clip, "with_position", _position)
        except Exception:
            return clip

    def _make_typewriter_clips(
        self,
        cue: SubtitleCue,
        effective_width: int,
        font_path: Optional[str],
        font_size: int,
        subtitle_color: str,
        params: Dict[str, Any],
        base_video: Any,
        project: Optional[Any] = None,
    ) -> list[Any]:
        """Split cue into one ImageClip per revealed-character step."""
        chars_per_second = float(params.get("chars_per_second", 20))
        full_text = cue.text
        total_chars = len(full_text)
        if total_chars == 0 or chars_per_second <= 0:
            return []

        clips: list[Any] = []
        char_duration = 1.0 / chars_per_second
        reveal_end = cue.start

        for n in range(1, total_chars + 1):
            t_start = cue.start + (n - 1) * char_duration
            t_end = cue.start + n * char_duration
            if t_start >= cue.end:
                break
            t_end = min(t_end, cue.end)

            partial_text = full_text[:n]
            image = self._make_subtitle_image(
                partial_text, effective_width, font_path, font_size,
                subtitle_color, cue.spans, cue.effects,
            )
            sc = ImageClip(np.array(image))
            sc = self._set_clip_duration(sc, max(0.01, t_end - t_start))
            sc = self._clip_call(sc, "with_start", t_start)
            sc = self._clip_call(sc, "with_end", t_end)
            y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
            x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))
            sc = self._clip_call(sc, "with_position", (x_pos, y_pos))
            clips.append(sc)
            reveal_end = t_end

        if reveal_end < cue.end:
            image = self._make_subtitle_image(
                full_text, effective_width, font_path, font_size,
                subtitle_color, cue.spans, cue.effects,
            )
            tail_clip = ImageClip(np.array(image))
            tail_clip = self._set_clip_duration(tail_clip, max(0.01, cue.end - reveal_end))
            tail_clip = self._clip_call(tail_clip, "with_start", reveal_end)
            tail_clip = self._clip_call(tail_clip, "with_end", cue.end)
            y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
            x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))
            tail_clip = self._clip_call(tail_clip, "with_position", (x_pos, y_pos))
            clips.append(tail_clip)

        return clips

    def render_project(
        self,
        project_path: str,
        output_path: Optional[str] = None,
        track_id: Optional[str] = None,
        font_path: Optional[str] = None,
        font_size: int = 36,
        subtitle_color: str = "white",
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        render_tracks: list[Track] = []
        if track_id:
            selected_track = project.find_track(track_id)
            if selected_track is not None and selected_track.kind == "video" and selected_track.visible and selected_track.clips:
                render_tracks.append(selected_track)
        else:
            render_tracks = [item for item in project.timeline.tracks if item.kind == "video" and item.visible and item.clips]

        if not render_tracks:
            return self._failure(
                "render_project",
                "No timeline track available for rendering",
                code="timeline.track.missing",
                path=str(Path(project_path)),
            )

        composite = None
        base_video = None
        rendered_clips: list[Any] = []
        opened_media: list[Any] = []
        subtitle_layers: list[Any] = []
        try:
            canvas_width, canvas_height, fps = self._project_canvas(project, project_path)
            timeline_duration = max(
                float(project.timeline.duration or 0.0),
                max(float(item.end) for track in render_tracks for item in track.clips),
            )

            for track in render_tracks:
                for clip in sorted(track.clips, key=lambda item: (item.start, item.end, item.id)):
                    media_clip, opened = self._build_timeline_video_clip(project, clip, project_path)
                    rendered_clips.append(media_clip)
                    opened_media.extend(opened)

            if not rendered_clips:
                return self._failure(
                    "render_project",
                    "No renderable clips were found on the timeline",
                    code="timeline.clip.missing",
                    path=str(Path(project_path)),
                )

            base_video = CompositeVideoClip(rendered_clips, size=(canvas_width, canvas_height))
            base_video = self._set_clip_duration(base_video, timeline_duration)
            if project.subtitles:
                for cue in project.subtitles:
                    _ml = int(cue.margin_left if cue.margin_left is not None else (cue.metadata.get("margin_left") or 20))
                    _mr = int(cue.margin_right if cue.margin_right is not None else (cue.metadata.get("margin_right") or 20))
                    effective_width = max(100, int(base_video.w) - _ml - _mr)
                    # Per-cue font overrides
                    cue_font_size = cue.font_size if cue.font_size else font_size
                    cue_font_path = cue.font_path if cue.font_path else font_path
                    image = self._make_subtitle_image(
                        cue.text, effective_width, cue_font_path, cue_font_size,
                        subtitle_color, cue.spans, cue.effects or [],
                    )
                    cue_duration = max(0.01, cue.end - cue.start)
                    fx_map = {fx.kind: fx.parameters for fx in (cue.effects or [])}

                    # --- typewriter: generate per-character clips ---
                    if "typewriter" in fx_map:
                        tw_clips = self._make_typewriter_clips(
                            cue, effective_width, cue_font_path, cue_font_size,
                            subtitle_color, fx_map["typewriter"],
                            base_video,
                            project=project,
                        )
                        subtitle_layers.extend(tw_clips)
                        continue

                    subtitle_clip = ImageClip(np.array(image))
                    subtitle_clip = self._set_clip_duration(subtitle_clip, cue_duration)
                    subtitle_clip = self._clip_call(subtitle_clip, "with_start", cue.start)
                    subtitle_clip = self._clip_call(subtitle_clip, "with_end", cue.end)
                    y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
                    x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))

                    # --- slide_in animation ---
                    if "slide_in" in fx_map:
                        subtitle_clip = self._apply_slide_anim(
                            subtitle_clip, fx_map["slide_in"], x_pos, y_pos,
                            cue.start, mode="in",
                        )
                    # --- slide_out animation ---
                    elif "slide_out" in fx_map:
                        subtitle_clip = self._apply_slide_anim(
                            subtitle_clip, fx_map["slide_out"], x_pos, y_pos,
                            cue.end, mode="out",
                        )
                    else:
                        subtitle_clip = self._clip_call(subtitle_clip, "with_position", (x_pos, y_pos))

                    # --- scale_in animation ---
                    if "scale_in" in fx_map:
                        subtitle_clip = self._apply_scale_in(subtitle_clip, fx_map["scale_in"], x_pos, y_pos)

                    # --- fade_in / fade_out ---
                    fx_list = []
                    if "fade_in" in fx_map:
                        fade_dur = float(fx_map["fade_in"].get("duration", 0.3))
                        fx_list.append(CrossFadeIn(fade_dur))
                    if "fade_out" in fx_map:
                        fade_dur = float(fx_map["fade_out"].get("duration", 0.3))
                        fx_list.append(CrossFadeOut(fade_dur))
                    
                    if hasattr(subtitle_clip, "with_effects") and fx_list:
                        subtitle_clip = subtitle_clip.with_effects(fx_list)
                    elif hasattr(subtitle_clip, "crossfadein"): # fallback for old moviepy just in case
                        if "fade_in" in fx_map:
                            fade_dur = float(fx_map["fade_in"].get("duration", 0.3))
                            subtitle_clip = self._clip_call(subtitle_clip, "crossfadein", fade_dur)
                        if "fade_out" in fx_map:
                            fade_dur = float(fx_map["fade_out"].get("duration", 0.3))
                            subtitle_clip = self._clip_call(subtitle_clip, "crossfadeout", fade_dur)

                    subtitle_layers.append(subtitle_clip)

                composite = CompositeVideoClip([base_video, *subtitle_layers], size=(base_video.w, base_video.h))
            else:
                composite = base_video

            project_workspace = self.store.workspace_for_project(project_path)
            project_workspace.ensure()
            target_output = Path(output_path).resolve() if output_path else project_workspace.default_export_path(project.name)
            Path(target_output).parent.mkdir(parents=True, exist_ok=True)
            render_output = target_output
            temp_output: Optional[Path] = None
            if any(ord(char) > 127 for char in str(target_output)):
                fd, temp_output_str = tempfile.mkstemp(
                    dir=str(target_output.parent),
                    prefix="aiclip_render_",
                    suffix=target_output.suffix or ".mp4",
                )
                os.close(fd)
                temp_output = Path(temp_output_str)
                temp_output.unlink(missing_ok=True)
                render_output = temp_output

            composite.write_videofile(str(render_output), fps=fps, codec="libx264", audio_codec="aac")
            if temp_output is not None:
                os.replace(temp_output, target_output)
        except Exception as exc:
            return self._failure(
                "render_project",
                f"Failed to render project: {exc}",
                code="render.failed",
                path=str(Path(output_path) if output_path else Path(project_path).resolve().parent / "exports"),
            )
        finally:
            for item in subtitle_layers:
                close = getattr(item, "close", None)
                if callable(close):
                    close()
            for item in rendered_clips:
                close = getattr(item, "close", None)
                if callable(close):
                    close()
            for item in opened_media:
                close = getattr(item, "close", None)
                if callable(close):
                    close()
            if base_video is not None:
                close = getattr(base_video, "close", None)
                if callable(close):
                    close()
            if composite is not None:
                close = getattr(composite, "close", None)
                if callable(close):
                    close()

        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="render.completed",
            message="Project rendered",
            operation="render_project",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors], final_path=str(target_output)),
            artifacts=[ArtifactRef(type="video", path=str(target_output)), ArtifactRef(type="project", path=str(Path(project_path)))],
            state={"project_path": str(Path(project_path)), "final_path": str(target_output)},
            payload=project.to_dict(),
            summary=f"Rendered project to {target_output}",
        ).to_dict()

    def add_project_audio_stem(
        self,
        project_path: str,
        stem_id: str,
        role: str,
        asset_path: str,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = AddAudioStemCommand(
            AudioStem(
                id=stem_id,
                role=role,
                path=asset_path,
                track_id=track_id,
            )
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_audio_stem",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="audio_stem.added",
            message="Audio stem added",
            operation="add_project_audio_stem",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added audio stem {stem_id}",
        ).to_dict()

    def update_project_audio_stem(
        self,
        project_path: str,
        stem_id: str,
        role: Optional[str] = None,
        asset_path: Optional[str] = None,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = UpdateAudioStemCommand(
            stem_id=stem_id,
            role=role,
            path=asset_path,
            track_id=track_id,
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="update_project_audio_stem",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="audio_stem.updated",
            message="Audio stem updated",
            operation="update_project_audio_stem",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated audio stem {stem_id}",
        ).to_dict()

    def remove_project_audio_stem(
        self,
        project_path: str,
        stem_id: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = RemoveAudioStemCommand(stem_id)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="remove_project_audio_stem",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="audio_stem.removed",
            message="Audio stem removed",
            operation="remove_project_audio_stem",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Removed audio stem {stem_id}",
        ).to_dict()

    def set_project_export_preset(
        self,
        project_path: str,
        preset_id: str,
        name: str,
        format: str,
        settings: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = SetExportPresetCommand(
            ExportPreset(
                id=preset_id,
                name=name,
                format=format,
                settings=settings or {},
            )
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="set_project_export_preset",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="export_preset.updated",
            message="Export preset updated",
            operation="set_project_export_preset",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated export preset {preset_id}",
        ).to_dict()

    def plan_project_export(
        self,
        project_path: str,
        preset_id: str,
        output_dir: str,
        base_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        preset = next((item for item in project.export_presets if item.id == preset_id), None)
        if preset is None:
            return self._failure(
                "plan_project_export",
                f"Export preset not found: {preset_id}",
                code="export_preset.not_found",
                path=str(Path(project_path)),
            )

        report = self.store.validate(project)
        safe_name = base_name or project.name or project.id
        export_dir = Path(output_dir)
        preview_path = export_dir / f"{safe_name}_preview.{preset.format}"
        final_path = export_dir / f"{safe_name}_final.{preset.format}"
        sidecar_path = export_dir / f"{safe_name}.json"

        render_ready = report.passed
        blockers = [issue.code for issue in report.errors]
        return ToolResult(
            ok=render_ready,
            status="ok" if render_ready else "warn",
            code="export.plan.ready" if render_ready else "export.plan.blocked",
            message="Export plan prepared" if render_ready else "Export plan blocked",
            operation="plan_project_export",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=render_ready,
                blockers=blockers,
                preview_path=str(preview_path),
                final_path=str(final_path),
            ),
            artifacts=[
                ArtifactRef(type="project", path=str(Path(project_path))),
                ArtifactRef(type="planned_preview", path=str(preview_path)),
                ArtifactRef(type="planned_final", path=str(final_path)),
                ArtifactRef(type="planned_sidecar", path=str(sidecar_path)),
            ],
            state={
                "project_path": str(Path(project_path)),
                "preset_id": preset.id,
                "preset_format": preset.format,
                "output_dir": str(export_dir),
                "preview_path": str(preview_path),
                "final_path": str(final_path),
                "sidecar_path": str(sidecar_path),
            },
            payload=project.to_dict(),
            next_actions=["fix_project", "revalidate"] if not render_ready else ["render_preview", "render_final"],
            summary=f"Planned export with preset {preset_id}",
        ).to_dict()

    def add_project_effect(
        self,
        project_path: str,
        effect_id: str,
        target_id: str,
        kind: str,
        parameters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = AddEffectCommand(
            Effect(
                id=effect_id,
                target_id=target_id,
                kind=kind,
                parameters=parameters or {},
            )
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_effect",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="effect.added",
            message="Effect added",
            operation="add_project_effect",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added effect {effect_id}",
        ).to_dict()

    def update_project_effect(
        self,
        project_path: str,
        effect_id: str,
        target_id: Optional[str] = None,
        kind: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = UpdateEffectCommand(
            effect_id=effect_id,
            target_id=target_id,
            kind=kind,
            parameters=parameters,
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="update_project_effect",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="effect.updated",
            message="Effect updated",
            operation="update_project_effect",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated effect {effect_id}",
        ).to_dict()

    def remove_project_effect(
        self,
        project_path: str,
        effect_id: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = RemoveEffectCommand(effect_id)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="remove_project_effect",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="effect.removed",
            message="Effect removed",
            operation="remove_project_effect",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Removed effect {effect_id}",
        ).to_dict()

    def add_project_comment(
        self,
        project_path: str,
        comment_id: str,
        author: str,
        text: str,
        anchor: Optional[str] = None,
        timecode: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = AddCommentCommand(
            Comment(
                id=comment_id,
                author=author,
                text=text,
                anchor=anchor,
                timecode=timecode,
            )
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_comment",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="comment.added",
            message="Comment added",
            operation="add_project_comment",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added comment {comment_id}",
        ).to_dict()

    def update_project_comment(
        self,
        project_path: str,
        comment_id: str,
        text: Optional[str] = None,
        anchor: Optional[str] = None,
        timecode: Optional[float] = None,
        locked: Optional[bool] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = UpdateCommentCommand(
            comment_id=comment_id,
            text=text,
            anchor=anchor,
            timecode=timecode,
            locked=locked,
        )
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="update_project_comment",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="comment.updated",
            message="Comment updated",
            operation="update_project_comment",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated comment {comment_id}",
        ).to_dict()

    def remove_project_comment(
        self,
        project_path: str,
        comment_id: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = RemoveCommentCommand(comment_id)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="remove_project_comment",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="comment.removed",
            message="Comment removed",
            operation="remove_project_comment",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Removed comment {comment_id}",
        ).to_dict()

    def lock_project_comment(
        self,
        project_path: str,
        comment_id: str,
        locked: bool = True,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = LockCommentCommand(comment_id, locked=locked)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="lock_project_comment",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="comment.locked" if locked else "comment.unlocked",
            message="Comment lock updated",
            operation="lock_project_comment",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"{'Locked' if locked else 'Unlocked'} comment {comment_id}",
        ).to_dict()

    def prepare_project_render(
        self,
        project_path: str,
        preview_path: Optional[str] = None,
        final_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        report = self.store.validate(project)
        render_ready = report.passed
        render_state = RenderState(
            ready=render_ready,
            blockers=[issue.code for issue in report.errors],
            preview_path=preview_path,
            final_path=final_path,
        )
        return ToolResult(
            ok=render_ready,
            status="ok" if render_ready else "warn",
            code="render.plan.ready" if render_ready else "render.plan.blocked",
            message="Render plan prepared" if render_ready else "Render plan blocked",
            operation="prepare_project_render",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=render_state,
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "preview_path": preview_path,
                "final_path": final_path,
            },
            payload=project.to_dict(),
            next_actions=["fix_project", "revalidate"] if not render_ready else ["render_final"],
            summary="Render plan prepared" if render_ready else "Render blocked by validation errors",
        ).to_dict()

    def set_project_metadata(
        self,
        project_path: str,
        metadata: Dict[str, Any],
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure

        command = SetProjectMetadataCommand(metadata)
        result = command.execute(project)
        if not result.ok:
            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="set_project_metadata",
                project_id=project.id,
                project_version=project.version,
                validation=result.validation,
                render_state=RenderState(ready=False, blockers=list(result.validation.errors)),
                state=result.state,
                summary=result.message,
                error=result.message,
            ).to_dict()

        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.metadata.updated",
            message="Project metadata updated",
            operation="set_project_metadata",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary="Updated project metadata",
        ).to_dict()
