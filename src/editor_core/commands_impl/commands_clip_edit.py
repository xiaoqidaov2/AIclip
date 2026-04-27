from __future__ import annotations

from typing import Any, Dict, Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Project


class TrimClipCommand(Command):
    name = "trim_clip"

    def __init__(self, clip_id: str, start: float, end: float, track_id: Optional[str] = None):
        self.clip_id = clip_id
        self.track_id = track_id
        self.start = start
        self.end = end

    def execute(self, project: Project) -> CommandResult:
        if self.start >= self.end:
            return CommandResult(ok=False, code="clip.range.invalid", message="Clip trim range is invalid", validation=ValidationSnapshot(passed=False, errors=["start must be less than end"]))
        track = project.find_track(self.track_id) if self.track_id else None
        clip = next((item for item in track.clips if item.id == self.clip_id), None) if track is not None else project.find_clip(self.clip_id)
        if clip is not None and track is None:
            track = next((item for item in project.timeline.tracks if clip in item.clips), None)
        if clip is None or track is None:
            return CommandResult(ok=False, code="clip.not_found", message=f"Clip not found: {self.clip_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing clip: {self.clip_id}"]))
        before = {"start": clip.start, "end": clip.end}
        clip.start = self.start
        clip.end = self.end
        project.bump_version()
        return CommandResult(ok=True, code="clip.trimmed", message="Clip trimmed", changes=[ToolChange(type="clip", id=self.clip_id, field="range", before=before, after={"start": clip.start, "end": clip.end}, details={"track_id": track.id})], state={"project_version": project.version, "track_id": track.id})


class SetClipSpeedCommand(Command):
    name = "set_clip_speed"

    def __init__(self, clip_id: str, speed: float, track_id: Optional[str] = None):
        self.clip_id = clip_id
        self.track_id = track_id
        self.speed = speed

    def execute(self, project: Project) -> CommandResult:
        if self.speed <= 0:
            return CommandResult(ok=False, code="clip.speed.invalid", message="Clip speed must be greater than zero", validation=ValidationSnapshot(passed=False, errors=["speed must be > 0"]))
        track = project.find_track(self.track_id) if self.track_id else None
        clip = next((item for item in track.clips if item.id == self.clip_id), None) if track is not None else project.find_clip(self.clip_id)
        if clip is not None and track is None:
            track = next((item for item in project.timeline.tracks if clip in item.clips), None)
        if clip is None:
            return CommandResult(ok=False, code="clip.not_found", message=f"Clip not found: {self.clip_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing clip: {self.clip_id}"]))
        before = clip.speed
        clip.speed = self.speed
        project.bump_version()
        return CommandResult(ok=True, code="clip.speed.updated", message="Clip speed updated", changes=[ToolChange(type="clip", id=self.clip_id, field="speed", before=before, after=clip.speed, details={"track_id": track.id if track else None})], state={"project_version": project.version, "track_id": track.id if track else None})


class SetClipTransformCommand(Command):
    name = "set_clip_transform"

    def __init__(self, clip_id: str, transform: Dict[str, Any], track_id: Optional[str] = None):
        self.clip_id = clip_id
        self.track_id = track_id
        self.transform = dict(transform or {})

    def execute(self, project: Project) -> CommandResult:
        track = project.find_track(self.track_id) if self.track_id else None
        clip = next((item for item in track.clips if item.id == self.clip_id), None) if track is not None else project.find_clip(self.clip_id)
        if clip is not None and track is None:
            track = next((item for item in project.timeline.tracks if clip in item.clips), None)
        if clip is None:
            return CommandResult(
                ok=False,
                code="clip.not_found",
                message=f"Clip not found: {self.clip_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing clip: {self.clip_id}"]),
            )

        before = dict(clip.transform or {})
        clip.transform.update(self.transform)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="clip.transform.updated",
            message="Clip transform updated",
            changes=[
                ToolChange(
                    type="clip",
                    id=self.clip_id,
                    field="transform",
                    before=before,
                    after=dict(clip.transform),
                    details={"track_id": track.id if track else None},
                )
            ],
            state={"project_version": project.version, "track_id": track.id if track else None},
        )
