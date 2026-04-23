from __future__ import annotations

from typing import Any, Dict, Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Project, SubtitleCue, SubtitleEffect, SubtitleSpan


class SetSubtitleEffectCommand(Command):
    name = "set_subtitle_effect"

    def __init__(self, cue_id: str, kind: str, parameters: Optional[Dict[str, Any]] = None, replace: bool = True, span_id: Optional[str] = None):
        self.cue_id = cue_id
        self.kind = kind
        self.parameters = parameters or {}
        self.replace = replace
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        target: SubtitleCue | SubtitleSpan = cue
        if self.span_id:
            span_target = next((item for item in cue.spans if item.id == self.span_id), None)
            if span_target is None:
                return CommandResult(ok=False, code="subtitle.span.not_found", message=f"Subtitle span not found: {self.span_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]))
            target = span_target
        before = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]
        if self.replace:
            target.effects = [fx for fx in target.effects if fx.kind != self.kind]
        target.effects.append(SubtitleEffect(kind=self.kind, parameters=dict(self.parameters)))
        project.bump_version()
        after = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]
        return CommandResult(ok=True, code="subtitle.effect.set", message=f"Subtitle effect '{self.kind}' set on target {self.span_id or self.cue_id}", changes=[ToolChange(type="subtitle_span" if self.span_id else "subtitle_cue", id=self.span_id or self.cue_id, field="effects", before=before, after=after)], state={"project_version": project.version, "effect_kind": self.kind})


class RemoveSubtitleEffectCommand(Command):
    name = "remove_subtitle_effect"

    def __init__(self, cue_id: str, kind: Optional[str] = None, span_id: Optional[str] = None):
        self.cue_id = cue_id
        self.kind = kind
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(ok=False, code="subtitle.not_found", message=f"Subtitle cue not found: {self.cue_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]))
        target: SubtitleCue | SubtitleSpan = cue
        if self.span_id:
            span_target = next((item for item in cue.spans if item.id == self.span_id), None)
            if span_target is None:
                return CommandResult(ok=False, code="subtitle.span.not_found", message=f"Subtitle span not found: {self.span_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]))
            target = span_target
        before = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]
        if self.kind is None:
            target.effects.clear()
        else:
            target.effects = [fx for fx in target.effects if fx.kind != self.kind]
        project.bump_version()
        return CommandResult(ok=True, code="subtitle.effect.removed", message=f"Subtitle effect(s) removed from target {self.span_id or self.cue_id}", changes=[ToolChange(type="subtitle_span" if self.span_id else "subtitle_cue", id=self.span_id or self.cue_id, field="effects", before=before, after=[{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects])], state={"project_version": project.version})
