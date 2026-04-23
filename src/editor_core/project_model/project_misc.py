from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .project_assets import Asset, Clip, Timeline, Track
from .project_helpers import filter_known_fields, list_of_dicts, now_iso
from .project_subtitles import SubtitleCue


@dataclass
class AudioStem:
    id: str
    role: str
    path: str
    track_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioStem":
        return cls(**filter_known_fields(cls, data))


@dataclass
class Effect:
    id: str
    target_id: str
    kind: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Effect":
        return cls(**filter_known_fields(cls, data))


@dataclass
class Comment:
    id: str
    author: str
    text: str
    anchor: Optional[str] = None
    timecode: Optional[float] = None
    locked: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Comment":
        return cls(**filter_known_fields(cls, data))


@dataclass
class ExportPreset:
    id: str
    name: str
    format: str
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportPreset":
        return cls(**filter_known_fields(cls, data))


@dataclass
class Project:
    id: str
    name: str
    version: int = 1
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    assets: List[Asset] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    subtitles: List[SubtitleCue] = field(default_factory=list)
    audio_stems: List[AudioStem] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    export_presets: List[ExportPreset] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        next_updated_at = datetime.now(timezone.utc)
        try:
            current_updated_at = datetime.fromisoformat(self.updated_at)
            # Normalise naive datetimes (no timezone) to UTC so comparison is safe.
            if current_updated_at.tzinfo is None:
                current_updated_at = current_updated_at.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            current_updated_at = None
        if current_updated_at is not None and next_updated_at <= current_updated_at:
            next_updated_at = current_updated_at + timedelta(microseconds=1)
        self.updated_at = next_updated_at.isoformat()

    def bump_version(self) -> None:
        self.version += 1
        self.touch()

    def find_asset(self, asset_id: str) -> Optional[Asset]:
        return next((asset for asset in self.assets if asset.id == asset_id), None)

    def find_track(self, track_id: str) -> Optional[Track]:
        return next((track for track in self.timeline.tracks if track.id == track_id), None)

    def find_clip(self, clip_id: str) -> Optional[Clip]:
        for track in self.timeline.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return clip
        return None

    def find_track_for_clip(self, clip_id: str) -> Optional[Track]:
        for track in self.timeline.tracks:
            for clip in track.clips:
                if clip.id == clip_id:
                    return track
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        items = dict(data)
        items["assets"] = list_of_dicts(items.get("assets"), Asset)
        items["timeline"] = Timeline.from_dict(items.get("timeline") or {})
        items["subtitles"] = list_of_dicts(items.get("subtitles"), SubtitleCue)
        items["audio_stems"] = list_of_dicts(items.get("audio_stems"), AudioStem)
        items["effects"] = list_of_dicts(items.get("effects"), Effect)
        items["comments"] = list_of_dicts(items.get("comments"), Comment)
        items["export_presets"] = list_of_dicts(items.get("export_presets"), ExportPreset)
        return cls(**filter_known_fields(cls, items))
