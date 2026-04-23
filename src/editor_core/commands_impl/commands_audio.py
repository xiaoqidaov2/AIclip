from __future__ import annotations

from typing import Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import AudioStem, Project


class AddAudioStemCommand(Command):
    name = "add_audio_stem"

    def __init__(self, stem: AudioStem):
        self.stem = stem

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.stem.id for item in project.audio_stems):
            return CommandResult(ok=False, code="audio_stem.duplicate", message=f"Audio stem already exists: {self.stem.id}", validation=ValidationSnapshot(passed=False, errors=[f"Duplicate audio stem id: {self.stem.id}"]))
        project.audio_stems.append(self.stem)
        project.bump_version()
        return CommandResult(ok=True, code="audio_stem.added", message="Audio stem added", changes=[ToolChange(type="audio_stem", id=self.stem.id, field="audio_stems", after=self.stem)], state={"project_version": project.version})


class UpdateAudioStemCommand(Command):
    name = "update_audio_stem"

    def __init__(self, stem_id: str, role: Optional[str] = None, path: Optional[str] = None, track_id: Optional[str] = None):
        self.stem_id = stem_id
        self.role = role
        self.path = path
        self.track_id = track_id

    def execute(self, project: Project) -> CommandResult:
        stem = next((item for item in project.audio_stems if item.id == self.stem_id), None)
        if stem is None:
            return CommandResult(ok=False, code="audio_stem.not_found", message=f"Audio stem not found: {self.stem_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing audio stem: {self.stem_id}"]))
        before = stem.__dict__.copy()
        for attr in ("role", "path", "track_id"):
            value = getattr(self, attr)
            if value is not None:
                setattr(stem, attr, value)
        project.bump_version()
        return CommandResult(ok=True, code="audio_stem.updated", message="Audio stem updated", changes=[ToolChange(type="audio_stem", id=self.stem_id, field="audio_stem", before=before, after=stem)], state={"project_version": project.version})


class RemoveAudioStemCommand(Command):
    name = "remove_audio_stem"

    def __init__(self, stem_id: str):
        self.stem_id = stem_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.audio_stems) if item.id == self.stem_id), None)
        if index is None:
            return CommandResult(ok=False, code="audio_stem.not_found", message=f"Audio stem not found: {self.stem_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing audio stem: {self.stem_id}"]))
        removed = project.audio_stems.pop(index)
        project.bump_version()
        return CommandResult(ok=True, code="audio_stem.removed", message="Audio stem removed", changes=[ToolChange(type="audio_stem", id=self.stem_id, field="audio_stems", before=removed)], state={"project_version": project.version})
