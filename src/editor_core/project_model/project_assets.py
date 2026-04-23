from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .project_helpers import filter_known_fields, list_of_dicts


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
        return cls(**filter_known_fields(cls, data))


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
        return cls(**filter_known_fields(cls, data))


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
        items["clips"] = list_of_dicts(items.get("clips"), Clip)
        return cls(**filter_known_fields(cls, items))


@dataclass
class Timeline:
    duration: float = 0.0
    fps: Optional[float] = None
    tracks: List[Track] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Timeline":
        items = dict(data)
        items["tracks"] = list_of_dicts(items.get("tracks"), Track)
        return cls(**filter_known_fields(cls, items))
