from __future__ import annotations

from typing import Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Clip, Project, Track


class AddClipCommand(Command):
    name = "add_clip"

    def __init__(self, clip: Clip, track_id: str, track_kind: str = "video", track_name: str = "", create_track: bool = True, insert_index: Optional[int] = None):
        self.clip = clip
        self.track_id = track_id
        self.track_kind = track_kind
        self.track_name = track_name
        self.create_track = create_track
        self.insert_index = insert_index

    def execute(self, project: Project) -> CommandResult:
        if project.find_clip(self.clip.id):
            return CommandResult(ok=False, code="clip.duplicate", message=f"Clip already exists: {self.clip.id}", validation=ValidationSnapshot(passed=False, errors=[f"Duplicate clip id: {self.clip.id}"]))
        if not project.find_asset(self.clip.asset_id):
            return CommandResult(ok=False, code="clip.asset.missing", message=f"Asset not found: {self.clip.asset_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing asset id: {self.clip.asset_id}"]))
        if self.clip.start < 0 or self.clip.end <= self.clip.start:
            return CommandResult(ok=False, code="clip.range.invalid", message="Clip start/end range is invalid", validation=ValidationSnapshot(passed=False, errors=["start must be >= 0 and end must be > start"]))
        track = project.find_track(self.track_id)
        created_track = None
        if track is None:
            if not self.create_track:
                return CommandResult(ok=False, code="track.not_found", message=f"Track not found: {self.track_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing track id: {self.track_id}"]))
            track = Track(id=self.track_id, kind=self.track_kind, name=self.track_name or self.track_id)
            project.timeline.tracks.append(track)
            created_track = track
        before_ids = [item.id for item in track.clips]
        if self.insert_index is None or self.insert_index >= len(track.clips):
            track.clips.append(self.clip)
        else:
            track.clips.insert(max(0, self.insert_index), self.clip)
        track.clips.sort(key=lambda item: (item.start, item.end, item.id))
        project.timeline.duration = max(float(project.timeline.duration or 0.0), float(self.clip.end))
        project.bump_version()
        changes = [ToolChange(type="clip", id=self.clip.id, field="clips", before=before_ids, after=[item.id for item in track.clips], details={"track_id": track.id, "asset_id": self.clip.asset_id})]
        if created_track is not None:
            changes.insert(0, ToolChange(type="track", id=created_track.id, field="tracks", after=created_track))
        return CommandResult(ok=True, code="clip.added", message="Clip added", changes=changes, state={"project_version": project.version, "track_id": track.id})
