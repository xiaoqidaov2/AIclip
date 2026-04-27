from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.editor_core.project import Project, SubtitleCue, SubtitleSpan, Track
from src.editor_core.store import ProjectStore


class ProjectToolTimeMixin:
    store: ProjectStore

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _resolve_media_path(
        self,
        project: Project,
        media_path: Optional[str] = None,
        project_path: Optional[str] = None,
    ) -> Optional[Path]:
        anchor = project_path or project.metadata.get("project_path") or "project.json"

        candidates: list[str] = []

        def add_candidate(value: Any) -> None:
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    candidates.append(cleaned)

        add_candidate(media_path)
        add_candidate(project.metadata.get("workspace_media_path"))
        for asset in project.assets:
            add_candidate(asset.metadata.get("workspace_media_path"))
            add_candidate(asset.path)
        add_candidate(project.metadata.get("source_media_path"))
        for asset in project.assets:
            add_candidate(asset.metadata.get("source_media_path"))

        seen: set[str] = set()
        for raw_candidate in candidates:
            key = os.path.normcase(raw_candidate) if os.name == "nt" else raw_candidate
            if key in seen:
                continue
            seen.add(key)

            try:
                candidate = self.store.resolve_asset_path(raw_candidate, anchor)
            except ValueError:
                continue

            if candidate.exists():
                return candidate
        return None

    def _project_main_track(
        self, project: Project, track_id: Optional[str] = None
    ) -> Optional[Track]:
        if track_id:
            track = project.find_track(track_id)
            if track is not None:
                return track
        for track in project.timeline.tracks:
            if track.kind in {"video", "audio"}:
                return track
        return project.timeline.tracks[0] if project.timeline.tracks else None

    def _merge_intervals(
        self, intervals: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
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

    def _remap_time(
        self, time_value: float, intervals: list[tuple[float, float]]
    ) -> float:
        elapsed = 0.0
        for start, end in intervals:
            if time_value < start:
                return elapsed
            if start <= time_value <= end:
                return elapsed + (time_value - start)
            elapsed += max(0.0, end - start)
        return elapsed

    def _subtitle_intervals(
        self, subtitles: list[SubtitleCue]
    ) -> list[tuple[float, float]]:
        return self._merge_intervals([(cue.start, cue.end) for cue in subtitles])

    def _normalize_subtitle_spans(
        self, cue_id: str, spans: list[dict[str, Any] | SubtitleSpan]
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
                self._validate_effect_entries(index, effects)
            normalized.append(normalized_entry)
        return normalized

    def _validate_effect_entries(self, entry_index: int, effects: list[Any]) -> None:
        for effect_index, effect in enumerate(effects, start=1):
            if not isinstance(effect, dict):
                raise ValueError(
                    f"entries[{entry_index}].effects[{effect_index}] must be an object"
                )
            kind = effect.get("kind")
            if not isinstance(kind, str) or not kind.strip():
                raise ValueError(
                    f"entries[{entry_index}].effects[{effect_index}].kind is required"
                )
            parameters = effect.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                raise ValueError(
                    f"entries[{entry_index}].effects[{effect_index}].parameters must be an object"
                )
