from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from ..contracts import ToolChange, ValidationSnapshot
from ..project import Project, SubtitleCue


def sync_cue_text_from_spans(cue: SubtitleCue) -> None:
    if cue.spans:
        cue.text = "".join(span.text for span in cue.spans)


@dataclass
class CommandResult:
    ok: bool
    code: str
    message: str
    changes: List[ToolChange] = field(default_factory=list)
    validation: ValidationSnapshot = field(default_factory=ValidationSnapshot)
    state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Command(ABC):
    name: str = "command"

    @abstractmethod
    def execute(self, project: Project) -> CommandResult:
        raise NotImplementedError
