from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .contracts import ToolChange, ValidationSnapshot
from .project import Asset, AudioStem, Clip, Comment, Effect, ExportPreset, Project, SubtitleCue, SubtitleEffect, SubtitleSpan, Track


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


class SetProjectMetadataCommand(Command):
    name = "set_project_metadata"

    def __init__(self, metadata: Dict[str, Any]):
        self.metadata = dict(metadata)

    def execute(self, project: Project) -> CommandResult:
        before = dict(project.metadata)
        project.metadata.update(self.metadata)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="project.metadata.updated",
            message="Project metadata updated",
            changes=[
                ToolChange(
                    type="project",
                    id=project.id,
                    field="metadata",
                    before=before,
                    after=dict(project.metadata),
                )
            ],
            state={"project_version": project.version},
        )


class AddAssetCommand(Command):
    name = "add_asset"

    def __init__(self, asset: Asset):
        self.asset = asset

    def execute(self, project: Project) -> CommandResult:
        if project.find_asset(self.asset.id):
            return CommandResult(
                ok=False,
                code="asset.duplicate",
                message=f"Asset already exists: {self.asset.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate asset id: {self.asset.id}"]),
            )

        project.assets.append(self.asset)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="asset.added",
            message="Asset added",
            changes=[
                ToolChange(
                    type="asset",
                    id=self.asset.id,
                    field="assets",
                    after=self.asset,
                )
            ],
            state={"project_version": project.version},
        )


class AddClipCommand(Command):
    name = "add_clip"

    def __init__(
        self,
        clip: Clip,
        track_id: str,
        track_kind: str = "video",
        track_name: str = "",
        create_track: bool = True,
        insert_index: Optional[int] = None,
    ):
        self.clip = clip
        self.track_id = track_id
        self.track_kind = track_kind
        self.track_name = track_name
        self.create_track = create_track
        self.insert_index = insert_index

    def execute(self, project: Project) -> CommandResult:
        if project.find_clip(self.clip.id):
            return CommandResult(
                ok=False,
                code="clip.duplicate",
                message=f"Clip already exists: {self.clip.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate clip id: {self.clip.id}"]),
            )

        if not project.find_asset(self.clip.asset_id):
            return CommandResult(
                ok=False,
                code="clip.asset.missing",
                message=f"Asset not found: {self.clip.asset_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing asset id: {self.clip.asset_id}"]),
            )

        if self.clip.start < 0 or self.clip.end <= self.clip.start:
            return CommandResult(
                ok=False,
                code="clip.range.invalid",
                message="Clip start/end range is invalid",
                validation=ValidationSnapshot(passed=False, errors=["start must be >= 0 and end must be > start"]),
            )

        track = project.find_track(self.track_id)
        created_track = None
        if track is None:
            if not self.create_track:
                return CommandResult(
                    ok=False,
                    code="track.not_found",
                    message=f"Track not found: {self.track_id}",
                    validation=ValidationSnapshot(passed=False, errors=[f"Missing track id: {self.track_id}"]),
                )
            track = Track(
                id=self.track_id,
                kind=self.track_kind,
                name=self.track_name or self.track_id,
            )
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

        changes = [
            ToolChange(
                type="clip",
                id=self.clip.id,
                field="clips",
                before=before_ids,
                after=[item.id for item in track.clips],
                details={"track_id": track.id, "asset_id": self.clip.asset_id},
            )
        ]
        if created_track is not None:
            changes.insert(
                0,
                ToolChange(
                    type="track",
                    id=created_track.id,
                    field="tracks",
                    after=created_track,
                ),
            )

        return CommandResult(
            ok=True,
            code="clip.added",
            message="Clip added",
            changes=changes,
            state={"project_version": project.version, "track_id": track.id},
        )


class TrimClipCommand(Command):
    name = "trim_clip"

    def __init__(self, clip_id: str, start: float, end: float, track_id: Optional[str] = None):
        self.clip_id = clip_id
        self.track_id = track_id
        self.start = start
        self.end = end

    def execute(self, project: Project) -> CommandResult:
        if self.start >= self.end:
            return CommandResult(
                ok=False,
                code="clip.range.invalid",
                message="Clip trim range is invalid",
                validation=ValidationSnapshot(passed=False, errors=["start must be less than end"]),
            )

        track = project.find_track(self.track_id) if self.track_id else None
        clip = None
        if track is not None:
            clip = next((item for item in track.clips if item.id == self.clip_id), None)
        else:
            clip = project.find_clip(self.clip_id)
            if clip is not None:
                track = next((item for item in project.timeline.tracks if clip in item.clips), None)

        if clip is None or track is None:
            return CommandResult(
                ok=False,
                code="clip.not_found",
                message=f"Clip not found: {self.clip_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing clip: {self.clip_id}"]),
            )

        before = {"start": clip.start, "end": clip.end}
        clip.start = self.start
        clip.end = self.end
        project.bump_version()
        return CommandResult(
            ok=True,
            code="clip.trimmed",
            message="Clip trimmed",
            changes=[
                ToolChange(
                    type="clip",
                    id=self.clip_id,
                    field="range",
                    before=before,
                    after={"start": clip.start, "end": clip.end},
                    details={"track_id": track.id},
                )
            ],
            state={"project_version": project.version, "track_id": track.id},
        )


class SetClipSpeedCommand(Command):
    name = "set_clip_speed"

    def __init__(self, clip_id: str, speed: float, track_id: Optional[str] = None):
        self.clip_id = clip_id
        self.track_id = track_id
        self.speed = speed

    def execute(self, project: Project) -> CommandResult:
        clip = None
        track = project.find_track(self.track_id) if self.track_id else None
        if track is not None:
            clip = next((item for item in track.clips if item.id == self.clip_id), None)
        else:
            clip = project.find_clip(self.clip_id)
            if clip is not None:
                track = next((item for item in project.timeline.tracks if clip in item.clips), None)

        if clip is None:
            return CommandResult(
                ok=False,
                code="clip.not_found",
                message=f"Clip not found: {self.clip_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing clip: {self.clip_id}"]),
            )

        before = clip.speed
        clip.speed = self.speed
        project.bump_version()
        return CommandResult(
            ok=True,
            code="clip.speed.updated",
            message="Clip speed updated",
            changes=[
                ToolChange(
                    type="clip",
                    id=self.clip_id,
                    field="speed",
                    before=before,
                    after=clip.speed,
                    details={"track_id": track.id if track else None},
                )
            ],
            state={"project_version": project.version, "track_id": track.id if track else None},
        )


class AddSubtitleCueCommand(Command):
    name = "add_subtitle_cue"

    def __init__(
        self,
        cue: SubtitleCue,
    ):
        self.cue = cue

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.cue.id for item in project.subtitles):
            return CommandResult(
                ok=False,
                code="subtitle.duplicate",
                message=f"Subtitle cue already exists: {self.cue.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate subtitle id: {self.cue.id}"]),
            )

        project.subtitles.append(self.cue)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle.added",
            message="Subtitle cue added",
            changes=[
                ToolChange(
                    type="subtitle",
                    id=self.cue.id,
                    field="subtitles",
                    after=self.cue,
                )
            ],
            state={"project_version": project.version},
        )


class UpdateSubtitleCueCommand(Command):
    name = "update_subtitle_cue"

    def __init__(
        self,
        cue_id: str,
        start: Optional[float] = None,
        end: Optional[float] = None,
        text: Optional[str] = None,
        spans: Optional[List[SubtitleSpan]] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        position: Optional[str] = None,
        margin_top: Optional[float] = None,
        margin_bottom: Optional[float] = None,
        margin_left: Optional[float] = None,
        margin_right: Optional[float] = None,
        offset_y: Optional[float] = None,
    ):
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
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        before = cue.__dict__.copy()
        if self.start is not None:
            cue.start = self.start
        if self.end is not None:
            cue.end = self.end
        if self.text is not None:
            cue.text = self.text
        if self.spans is not None:
            cue.spans = list(self.spans)
        if self.speaker is not None:
            cue.speaker = self.speaker
        if self.language is not None:
            cue.language = self.language
        if self.position is not None:
            cue.position = self.position
        if self.margin_top is not None:
            cue.margin_top = self.margin_top
        if self.margin_bottom is not None:
            cue.margin_bottom = self.margin_bottom
        if self.margin_left is not None:
            cue.margin_left = self.margin_left
        if self.margin_right is not None:
            cue.margin_right = self.margin_right
        if self.offset_y is not None:
            cue.offset_y = self.offset_y

        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle.updated",
            message="Subtitle cue updated",
            changes=[
                ToolChange(
                    type="subtitle",
                    id=self.cue_id,
                    field="subtitle",
                    before=before,
                    after=cue,
                )
            ],
            state={"project_version": project.version},
        )


class RemoveSubtitleCueCommand(Command):
    name = "remove_subtitle_cue"

    def __init__(self, cue_id: str):
        self.cue_id = cue_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.subtitles) if item.id == self.cue_id), None)
        if index is None:
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        removed = project.subtitles.pop(index)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle.removed",
            message="Subtitle cue removed",
            changes=[
                ToolChange(
                    type="subtitle",
                    id=self.cue_id,
                    field="subtitles",
                    before=removed,
                )
            ],
            state={"project_version": project.version},
        )


class AddSubtitleSpanCommand(Command):
    name = "add_subtitle_span"

    def __init__(self, cue_id: str, span: SubtitleSpan, index: Optional[int] = None):
        self.cue_id = cue_id
        self.span = span
        self.index = index

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        span = self.span
        if not span.id:
            span.id = f"{self.cue_id}_span_{len(cue.spans) + 1:03d}"

        before = [item.__dict__.copy() for item in cue.spans]
        if self.index is None or self.index >= len(cue.spans):
            cue.spans.append(span)
        else:
            cue.spans.insert(max(0, self.index), span)

        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle_span.added",
            message="Subtitle span added",
            changes=[
                ToolChange(
                    type="subtitle_span",
                    id=span.id,
                    field="spans",
                    before=before,
                    after=[item.__dict__.copy() for item in cue.spans],
                    details={"cue_id": self.cue_id, "index": self.index},
                )
            ],
            state={"project_version": project.version},
        )


class UpdateSubtitleSpanCommand(Command):
    name = "update_subtitle_span"

    def __init__(
        self,
        cue_id: str,
        span_id: str,
        text: Optional[str] = None,
        color: Optional[str] = None,
        bold: Optional[bool] = None,
        italic: Optional[bool] = None,
        underline: Optional[bool] = None,
    ):
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
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        span = next((item for item in cue.spans if item.id == self.span_id), None)
        if span is None:
            return CommandResult(
                ok=False,
                code="subtitle_span.not_found",
                message=f"Subtitle span not found: {self.span_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]),
            )

        before = span.__dict__.copy()
        if self.text is not None:
            span.text = self.text
        if self.color is not None:
            span.color = self.color
        if self.bold is not None:
            span.bold = self.bold
        if self.italic is not None:
            span.italic = self.italic
        if self.underline is not None:
            span.underline = self.underline

        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle_span.updated",
            message="Subtitle span updated",
            changes=[
                ToolChange(
                    type="subtitle_span",
                    id=span.id,
                    field="span",
                    before=before,
                    after=span,
                    details={"cue_id": self.cue_id},
                )
            ],
            state={"project_version": project.version},
        )


class RemoveSubtitleSpanCommand(Command):
    name = "remove_subtitle_span"

    def __init__(self, cue_id: str, span_id: str):
        self.cue_id = cue_id
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        index = next((i for i, item in enumerate(cue.spans) if item.id == self.span_id), None)
        if index is None:
            return CommandResult(
                ok=False,
                code="subtitle_span.not_found",
                message=f"Subtitle span not found: {self.span_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]),
            )

        removed = cue.spans.pop(index)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle_span.removed",
            message="Subtitle span removed",
            changes=[
                ToolChange(
                    type="subtitle_span",
                    id=removed.id,
                    field="spans",
                    before=removed,
                    details={"cue_id": self.cue_id, "index": index},
                )
            ],
            state={"project_version": project.version},
        )


class SetSubtitleEffectCommand(Command):
    """Add or replace a visual / animation effect on a subtitle cue or span.

    If *replace* is True, all existing effects with the same *kind* are removed
    first so only one effect of each kind exists per target.
    """

    name = "set_subtitle_effect"

    def __init__(
        self,
        cue_id: str,
        kind: str,
        parameters: Optional[Dict[str, Any]] = None,
        replace: bool = True,
        span_id: Optional[str] = None,
    ):
        self.cue_id = cue_id
        self.kind = kind
        self.parameters: Dict[str, Any] = parameters or {}
        self.replace = replace
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        target = cue
        if self.span_id:
            target = next((item for item in cue.spans if item.id == self.span_id), None)
            if target is None:
                return CommandResult(
                    ok=False,
                    code="subtitle.span.not_found",
                    message=f"Subtitle span not found: {self.span_id}",
                    validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]),
                )

        before = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]
        if self.replace:
            target.effects = [fx for fx in target.effects if fx.kind != self.kind]

        target.effects.append(SubtitleEffect(kind=self.kind, parameters=dict(self.parameters)))
        project.bump_version()
        after = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]

        return CommandResult(
            ok=True,
            code="subtitle.effect.set",
            message=f"Subtitle effect '{self.kind}' set on target {self.span_id or self.cue_id}",
            changes=[
                ToolChange(
                    type="subtitle_span" if self.span_id else "subtitle_cue",
                    id=self.span_id or self.cue_id,
                    field="effects",
                    before=before,
                    after=after,
                )
            ],
            state={"project_version": project.version, "effect_kind": self.kind},
        )


class RemoveSubtitleEffectCommand(Command):
    """Remove one or all effects of a given *kind* from a subtitle cue or span.

    If *kind* is None, every effect on the target is removed.
    """

    name = "remove_subtitle_effect"

    def __init__(self, cue_id: str, kind: Optional[str] = None, span_id: Optional[str] = None):
        self.cue_id = cue_id
        self.kind = kind
        self.span_id = span_id

    def execute(self, project: Project) -> CommandResult:
        cue = next((item for item in project.subtitles if item.id == self.cue_id), None)
        if cue is None:
            return CommandResult(
                ok=False,
                code="subtitle.not_found",
                message=f"Subtitle cue not found: {self.cue_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle cue: {self.cue_id}"]),
            )

        target = cue
        if self.span_id:
            target = next((item for item in cue.spans if item.id == self.span_id), None)
            if target is None:
                return CommandResult(
                    ok=False,
                    code="subtitle.span.not_found",
                    message=f"Subtitle span not found: {self.span_id}",
                    validation=ValidationSnapshot(passed=False, errors=[f"Missing subtitle span: {self.span_id}"]),
                )

        before = [{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects]
        if self.kind is None:
            target.effects.clear()
        else:
            target.effects = [fx for fx in target.effects if fx.kind != self.kind]

        project.bump_version()
        return CommandResult(
            ok=True,
            code="subtitle.effect.removed",
            message=f"Subtitle effect(s) removed from target {self.span_id or self.cue_id}",
            changes=[
                ToolChange(
                    type="subtitle_span" if self.span_id else "subtitle_cue",
                    id=self.span_id or self.cue_id,
                    field="effects",
                    before=before,
                    after=[{"kind": fx.kind, "parameters": dict(fx.parameters)} for fx in target.effects],
                )
            ],
            state={"project_version": project.version},
        )


class AddAudioStemCommand(Command):
    name = "add_audio_stem"

    def __init__(self, stem: AudioStem):
        self.stem = stem

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.stem.id for item in project.audio_stems):
            return CommandResult(
                ok=False,
                code="audio_stem.duplicate",
                message=f"Audio stem already exists: {self.stem.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate audio stem id: {self.stem.id}"]),
            )

        project.audio_stems.append(self.stem)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="audio_stem.added",
            message="Audio stem added",
            changes=[
                ToolChange(
                    type="audio_stem",
                    id=self.stem.id,
                    field="audio_stems",
                    after=self.stem,
                )
            ],
            state={"project_version": project.version},
        )


class UpdateAudioStemCommand(Command):
    name = "update_audio_stem"

    def __init__(
        self,
        stem_id: str,
        role: Optional[str] = None,
        path: Optional[str] = None,
        track_id: Optional[str] = None,
    ):
        self.stem_id = stem_id
        self.role = role
        self.path = path
        self.track_id = track_id

    def execute(self, project: Project) -> CommandResult:
        stem = next((item for item in project.audio_stems if item.id == self.stem_id), None)
        if stem is None:
            return CommandResult(
                ok=False,
                code="audio_stem.not_found",
                message=f"Audio stem not found: {self.stem_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing audio stem: {self.stem_id}"]),
            )

        before = stem.__dict__.copy()
        if self.role is not None:
            stem.role = self.role
        if self.path is not None:
            stem.path = self.path
        if self.track_id is not None:
            stem.track_id = self.track_id

        project.bump_version()
        return CommandResult(
            ok=True,
            code="audio_stem.updated",
            message="Audio stem updated",
            changes=[
                ToolChange(
                    type="audio_stem",
                    id=self.stem_id,
                    field="audio_stem",
                    before=before,
                    after=stem,
                )
            ],
            state={"project_version": project.version},
        )


class RemoveAudioStemCommand(Command):
    name = "remove_audio_stem"

    def __init__(self, stem_id: str):
        self.stem_id = stem_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.audio_stems) if item.id == self.stem_id), None)
        if index is None:
            return CommandResult(
                ok=False,
                code="audio_stem.not_found",
                message=f"Audio stem not found: {self.stem_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing audio stem: {self.stem_id}"]),
            )

        removed = project.audio_stems.pop(index)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="audio_stem.removed",
            message="Audio stem removed",
            changes=[
                ToolChange(
                    type="audio_stem",
                    id=self.stem_id,
                    field="audio_stems",
                    before=removed,
                )
            ],
            state={"project_version": project.version},
        )


class SetExportPresetCommand(Command):
    name = "set_export_preset"

    def __init__(self, preset: ExportPreset):
        self.preset = preset

    def execute(self, project: Project) -> CommandResult:
        existing = next((item for item in project.export_presets if item.id == self.preset.id), None)
        before = existing.__dict__.copy() if existing else None
        if existing is None:
            project.export_presets.append(self.preset)
        else:
            existing.name = self.preset.name
            existing.format = self.preset.format
            existing.settings.update(self.preset.settings)
            existing.metadata.update(self.preset.metadata)

        project.bump_version()
        return CommandResult(
            ok=True,
            code="export_preset.updated",
            message="Export preset updated",
            changes=[
                ToolChange(
                    type="export_preset",
                    id=self.preset.id,
                    field="export_presets",
                    before=before,
                    after=self.preset,
                )
            ],
            state={"project_version": project.version},
        )


class AddEffectCommand(Command):
    name = "add_effect"

    def __init__(self, effect: Effect):
        self.effect = effect

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.effect.id for item in project.effects):
            return CommandResult(
                ok=False,
                code="effect.duplicate",
                message=f"Effect already exists: {self.effect.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate effect id: {self.effect.id}"]),
            )

        project.effects.append(self.effect)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="effect.added",
            message="Effect added",
            changes=[
                ToolChange(
                    type="effect",
                    id=self.effect.id,
                    field="effects",
                    after=self.effect,
                )
            ],
            state={"project_version": project.version},
        )


class UpdateEffectCommand(Command):
    name = "update_effect"

    def __init__(
        self,
        effect_id: str,
        target_id: Optional[str] = None,
        kind: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        self.effect_id = effect_id
        self.target_id = target_id
        self.kind = kind
        self.parameters = parameters or {}

    def execute(self, project: Project) -> CommandResult:
        effect = next((item for item in project.effects if item.id == self.effect_id), None)
        if effect is None:
            return CommandResult(
                ok=False,
                code="effect.not_found",
                message=f"Effect not found: {self.effect_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing effect: {self.effect_id}"]),
            )

        before = effect.__dict__.copy()
        if self.target_id is not None:
            effect.target_id = self.target_id
        if self.kind is not None:
            effect.kind = self.kind
        if self.parameters:
            effect.parameters.update(self.parameters)

        project.bump_version()
        return CommandResult(
            ok=True,
            code="effect.updated",
            message="Effect updated",
            changes=[
                ToolChange(
                    type="effect",
                    id=self.effect_id,
                    field="effect",
                    before=before,
                    after=effect,
                )
            ],
            state={"project_version": project.version},
        )


class RemoveEffectCommand(Command):
    name = "remove_effect"

    def __init__(self, effect_id: str):
        self.effect_id = effect_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.effects) if item.id == self.effect_id), None)
        if index is None:
            return CommandResult(
                ok=False,
                code="effect.not_found",
                message=f"Effect not found: {self.effect_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing effect: {self.effect_id}"]),
            )

        removed = project.effects.pop(index)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="effect.removed",
            message="Effect removed",
            changes=[
                ToolChange(
                    type="effect",
                    id=self.effect_id,
                    field="effects",
                    before=removed,
                )
            ],
            state={"project_version": project.version},
        )


class AddCommentCommand(Command):
    name = "add_comment"

    def __init__(self, comment: Comment):
        self.comment = comment

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.comment.id for item in project.comments):
            return CommandResult(
                ok=False,
                code="comment.duplicate",
                message=f"Comment already exists: {self.comment.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate comment id: {self.comment.id}"]),
            )

        project.comments.append(self.comment)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="comment.added",
            message="Comment added",
            changes=[
                ToolChange(
                    type="comment",
                    id=self.comment.id,
                    field="comments",
                    after=self.comment,
                )
            ],
            state={"project_version": project.version},
        )


class UpdateCommentCommand(Command):
    name = "update_comment"

    def __init__(
        self,
        comment_id: str,
        text: Optional[str] = None,
        anchor: Optional[str] = None,
        timecode: Optional[float] = None,
        locked: Optional[bool] = None,
    ):
        self.comment_id = comment_id
        self.text = text
        self.anchor = anchor
        self.timecode = timecode
        self.locked = locked

    def execute(self, project: Project) -> CommandResult:
        comment = next((item for item in project.comments if item.id == self.comment_id), None)
        if comment is None:
            return CommandResult(
                ok=False,
                code="comment.not_found",
                message=f"Comment not found: {self.comment_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]),
            )

        before = comment.__dict__.copy()
        if self.text is not None:
            comment.text = self.text
        if self.anchor is not None:
            comment.anchor = self.anchor
        if self.timecode is not None:
            comment.timecode = self.timecode
        if self.locked is not None:
            comment.locked = self.locked

        project.bump_version()
        return CommandResult(
            ok=True,
            code="comment.updated",
            message="Comment updated",
            changes=[
                ToolChange(
                    type="comment",
                    id=self.comment_id,
                    field="comment",
                    before=before,
                    after=comment,
                )
            ],
            state={"project_version": project.version},
        )


class RemoveCommentCommand(Command):
    name = "remove_comment"

    def __init__(self, comment_id: str):
        self.comment_id = comment_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.comments) if item.id == self.comment_id), None)
        if index is None:
            return CommandResult(
                ok=False,
                code="comment.not_found",
                message=f"Comment not found: {self.comment_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]),
            )

        removed = project.comments.pop(index)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="comment.removed",
            message="Comment removed",
            changes=[
                ToolChange(
                    type="comment",
                    id=self.comment_id,
                    field="comments",
                    before=removed,
                )
            ],
            state={"project_version": project.version},
        )


class LockCommentCommand(Command):
    name = "lock_comment"

    def __init__(self, comment_id: str, locked: bool = True):
        self.comment_id = comment_id
        self.locked = locked

    def execute(self, project: Project) -> CommandResult:
        comment = next((item for item in project.comments if item.id == self.comment_id), None)
        if comment is None:
            return CommandResult(
                ok=False,
                code="comment.not_found",
                message=f"Comment not found: {self.comment_id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]),
            )

        before = comment.locked
        comment.locked = self.locked
        project.bump_version()
        return CommandResult(
            ok=True,
            code="comment.locked" if self.locked else "comment.unlocked",
            message="Comment lock updated",
            changes=[
                ToolChange(
                    type="comment",
                    id=self.comment_id,
                    field="locked",
                    before=before,
                    after=comment.locked,
                )
            ],
            state={"project_version": project.version},
        )
