from __future__ import annotations

from typing import List, Optional

from .commands_base import Command, CommandResult, sync_cue_text_from_spans
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Project, SubtitleCue, SubtitleSpan


class AddSubtitleCueCommand(Command):
    name = "add_subtitle_cue"

    def __init__(self, cue: SubtitleCue):
        self.cue = cue

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.cue.id for item in project.subtitles):
            return CommandResult(ok=False, code="subtitle.duplicate", message=f"Subtitle cue already exists: {self.cue.id}", validation=ValidationSnapshot(passed=False, errors=[f"Duplicate subtitle id: {self.cue.id}"]))
        sync_cue_text_from_spans(self.cue)
        project.subtitles.append(self.cue)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle.added", message="Subtitle cue added", changes=[ToolChange(type="subtitle", id=self.cue.id, field="subtitles", after=self.cue)], state={"project_version": project.version})


class UpdateSubtitleCueCommand(Command):
    name = "update_subtitle_cue"

    def __init__(self, cue_id: str, start: Optional[float] = None, end: Optional[float] = None, text: Optional[str] = None, spans: Optional[List[SubtitleSpan]] = None, speaker: Optional[str] = None, language: Optional[str] = None, position: Optional[str] = None, margin_top: Optional[float] = None, margin_bottom: Optional[float] = None, margin_left: Optional[float] = None, margin_right: Optional[float] = None, offset_y: Optional[float] = None):
        self.cue_id = cue_id
        self.start = start
        self.end = end
        self.text = text
        self.spans = spans
        self.speaker = speaker
        self.language = language
        self.position = position
        self.margin_top = margin_top
        self.margin_bottom = margin_bottom
        self.margin_left = margin_left
        self.margin_right = margin_right
        self.offset_y = offset_y

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        before = cue.__dict__.copy()
        for attr in ("start", "end", "text", "speaker", "language", "position", "margin_top", "margin_bottom", "margin_left", "margin_right", "offset_y"):
            value = getattr(self, attr)
            if value is not None:
                setattr(cue, attr, value)
        if self.spans is not None:
            cue.spans = list(self.spans)
            sync_cue_text_from_spans(cue)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle.updated", message="Subtitle cue updated", changes=[ToolChange(type="subtitle", id=self.cue_id, field="subtitle", before=before, after=cue)], state={"project_version": project.version})


class RemoveSubtitleCueCommand(Command):
    name = "remove_subtitle_cue"

    def __init__(self, cue_id: str):
        self.cue_id = cue_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.subtitles) if item.id == self.cue_id), None)
        if index is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        removed = project.subtitles.pop(index)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle.removed", message="Subtitle cue removed", changes=[ToolChange(type="subtitle", id=self.cue_id, field="subtitles", before=removed)], state={"project_version": project.version})
