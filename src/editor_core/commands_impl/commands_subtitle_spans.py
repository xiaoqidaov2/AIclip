from __future__ import annotations

from typing import Optional

from .commands_base import Command, CommandResult, sync_cue_text_from_spans
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Project, SubtitleSpan


class AddSubtitleSpanCommand(Command):
    name = "add_subtitle_span"

    def __init__(self, cue_id: str, span: SubtitleSpan, index: Optional[int] = None):
        self.cue_id = cue_id
        self.span = span
        self.index = index

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        span = self.span
        if not span.id:
            span.id = f"{self.cue_id}_span_{len(cue.spans) + 1:03d}"
        before = [item.__dict__.copy() for item in cue.spans]
        if self.index is None or self.index >= len(cue.spans):
            cue.spans.append(span)
        else:
            cue.spans.insert(max(0, self.index), span)
        sync_cue_text_from_spans(cue)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle_span.added", message="Subtitle span added", changes=[ToolChange(type="subtitle_span", id=span.id, field="spans", before=before, after=[item.__dict__.copy() for item in cue.spans], details={"cue_id": self.cue_id, "index": self.index})], state={"project_version": project.version})


class UpdateSubtitleSpanCommand(Command):
    name = "update_subtitle_span"

    def __init__(self, cue_id: str, span_id: str, text: Optional[str] = None, color: Optional[str] = None, bold: Optional[bool] = None, italic: Optional[bool] = None, underline: Optional[bool] = None):
        self.cue_id = cue_id
        self.span_id = span_id
        self.text = text
        self.color = color
        self.bold = bold
        self.italic = italic
        self.underline = underline

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        span = next((item for item in cue.spans if item.id == self.span_id), None)
        if span is None:
            return CommandResult(ok=False, code="subtitle_span.not_found", message=f"Subtitle span not found: {self.span_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]))
        before = span.__dict__.copy()
        for attr in ("text", "color", "bold", "italic", "underline"):
            value = getattr(self, attr)
            if value is not None:
                setattr(span, attr, value)
        sync_cue_text_from_spans(cue)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle_span.updated", message="Subtitle span updated", changes=[ToolChange(type="subtitle_span", id=span.id, field="span", before=before, after=span, details={"cue_id": self.cue_id})], state={"project_version": project.version})


class RemoveSubtitleSpanCommand(Command):
    name = "remove_subtitle_span"

    def __init__(self, cue_id: str, span_id: str):
        self.cue_id = cue_id
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        index = next((i for i, item in enumerate(cue.spans) if item.id == self.span_id), None)
        if index is None:
            return CommandResult(ok=False, code="subtitle_span.not_found", message=f"Subtitle span not found: {self.span_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]))
        removed = cue.spans.pop(index)
        sync_cue_text_from_spans(cue)
        project.bump_version()
        return CommandResult(ok=True, code="subtitle_span.removed", message="Subtitle span removed", changes=[ToolChange(type="subtitle_span", id=removed.id, field="spans", before=removed, details={"cue_id": self.cue_id, "index": index})], state={"project_version": project.version})
