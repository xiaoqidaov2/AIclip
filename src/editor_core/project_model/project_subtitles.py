from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .project_helpers import filter_known_fields, list_of_dicts


@dataclass
class SubtitleEffect:
    kind: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubtitleEffect":
        return cls(**filter_known_fields(cls, data))


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
        items["effects"] = list_of_dicts(items.get("effects"), SubtitleEffect)
        return cls(**filter_known_fields(cls, items))


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
        items["spans"] = list_of_dicts(items.get("spans"), SubtitleSpan)
        items["effects"] = list_of_dicts(items.get("effects"), SubtitleEffect)
        return cls(**filter_known_fields(cls, items))
