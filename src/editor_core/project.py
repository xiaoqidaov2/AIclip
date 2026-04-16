from __future__ import annotations

from dataclasses import asdict, dataclass, field
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_of_dicts(items: Any, cls):
    if not items:
        return []
    return [cls.from_dict(item) if isinstance(item, dict) else item for item in items]


def _filter_known_fields(cls, data: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {item.name for item in fields(cls)}
    return {key: value for key, value in data.items() if key in allowed}


@dataclass
class Asset:
    id: str
    path: str
    source: str = "local"
    media_type: str = "unknown"
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    versions: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Asset":
        return cls(**_filter_known_fields(cls, data))


@dataclass
class Clip:
    id: str
    asset_id: str
    start: float
    end: float
    source_in: float = 0.0
    source_out: Optional[float] = None
    speed: float = 1.0
    transform: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Clip":
        return cls(**_filter_known_fields(cls, data))


@dataclass
class Track:
    id: str
    kind: str
    name: str = ""
    clips: List[Clip] = field(default_factory=list)
    role: Optional[str] = None
    locked: bool = False
    visible: bool = True
    volume: float = 1.0
    muted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        items = dict(data)
        items["clips"] = _list_of_dicts(items.get("clips"), Clip)
        return cls(**_filter_known_fields(cls, items))


@dataclass
class Timeline:
    duration: float = 0.0
    fps: Optional[float] = None
    tracks: List[Track] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Timeline":
        items = dict(data)
        items["tracks"] = _list_of_dicts(items.get("tracks"), Track)
        return cls(**_filter_known_fields(cls, items))


@dataclass
class SubtitleSpan:
    text: str
    id: str = ""
    color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    effects: List[SubtitleEffect] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleSpan":
        items = dict(data)
        items["effects"] = _list_of_dicts(items.get("effects"), SubtitleEffect)
        return cls(**_filter_known_fields(cls, items))


@dataclass
class SubtitleEffect:
    """An animation or visual effect applied to a subtitle cue at render time.

    kind values
    -----------
    Visual (applied to the still image):
      - ``outline``        – text stroke; params: color (str), width (int, default 2)
      - ``glow``           – soft luminous halo; params: color (str, default "white"), radius (int, default 4)
      - ``background_box`` – filled rectangle behind text; params: color (str, default "black"), opacity (0-255, default 160), padding (int, default 8)
      - ``gradient``       – vertical or horizontal gradient fill; params: color_top (str), color_bottom (str), direction ("vertical"|"horizontal")

    Animation (applied to the clip in the render timeline):
      - ``fade_in``        – opacity ramp in; params: duration (float, seconds, default 0.3)
      - ``fade_out``       – opacity ramp out; params: duration (float, seconds, default 0.3)
      - ``slide_in``       – position animation on entry; params: direction ("bottom"|"top"|"left"|"right"), duration (float, default 0.3), distance (int px, default 40)
      - ``slide_out``      – position animation on exit; params: direction ("bottom"|"top"|"left"|"right"), duration (float, default 0.3), distance (int, default 40)
      - ``typewriter``     – reveal characters progressively; params: chars_per_second (float, default 20)
      - ``scale_in``       – zoom from 0 to full size; params: duration (float, default 0.3)
    """

    kind: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleEffect":
        return cls(**_filter_known_fields(cls, data))


@dataclass
class SubtitleCue:
    id: str
    start: float
    end: float
    text: str
    spans: List[SubtitleSpan] = field(default_factory=list)
    effects: List[SubtitleEffect] = field(default_factory=list)
    track_id: Optional[str] = None
    speaker: Optional[str] = None
    language: Optional[str] = None
    position: Optional[str] = None
    margin_top: Optional[float] = None
    margin_bottom: Optional[float] = None
    margin_left: Optional[float] = None
    margin_right: Optional[float] = None
    offset_y: float = 0.0
    font_size: Optional[int] = None
    font_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleCue":
        items = dict(data)
        items["spans"] = _list_of_dicts(items.get("spans"), SubtitleSpan)
        items["effects"] = _list_of_dicts(items.get("effects"), SubtitleEffect)
        return cls(**_filter_known_fields(cls, items))


@dataclass
class AudioStem:
    id: str
    role: str
    path: str
    track_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioStem":
        return cls(**_filter_known_fields(cls, data))


@dataclass
class Effect:
    id: str
    target_id: str
    kind: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Effect":
        return cls(**_filter_known_fields(cls, data))


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
        return cls(**_filter_known_fields(cls, data))


@dataclass
class ExportPreset:
    id: str
    name: str
    format: str
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportPreset":
        return cls(**_filter_known_fields(cls, data))


@dataclass
class Project:
    id: str
    name: str
    version: int = 1
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    assets: List[Asset] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    subtitles: List[SubtitleCue] = field(default_factory=list)
    audio_stems: List[AudioStem] = field(default_factory=list)
    effects: List[Effect] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    export_presets: List[ExportPreset] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.updated_at = _now_iso()

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
        items["assets"] = _list_of_dicts(items.get("assets"), Asset)
        items["timeline"] = Timeline.from_dict(items.get("timeline") or {})
        items["subtitles"] = _list_of_dicts(items.get("subtitles"), SubtitleCue)
        items["audio_stems"] = _list_of_dicts(items.get("audio_stems"), AudioStem)
        items["effects"] = _list_of_dicts(items.get("effects"), Effect)
        items["comments"] = _list_of_dicts(items.get("comments"), Comment)
        items["export_presets"] = _list_of_dicts(items.get("export_presets"), ExportPreset)
        return cls(**_filter_known_fields(cls, items))
