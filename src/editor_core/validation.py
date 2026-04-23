from __future__ import annotations


from dataclasses import dataclass, field


from typing import Any, Dict, List, Optional


from .project import Project


@dataclass
class ValidationIssue:

    severity: str

    code: str

    message: str

    path: Optional[str] = None

    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:

    passed: bool = True

    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def warnings(self) -> List[ValidationIssue]:

        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def errors(self) -> List[ValidationIssue]:

        return [issue for issue in self.issues if issue.severity == "error"]

    def add_issue(self, issue: ValidationIssue) -> None:

        self.issues.append(issue)

        self.passed = not any(item.severity == "error" for item in self.issues)


def validate_project(project: Project) -> ValidationReport:

    report = ValidationReport()

    if not project.id:

        report.add_issue(
            ValidationIssue("error", "project.id.missing", "Project id is required")
        )

    if not project.name:

        report.add_issue(
            ValidationIssue("error", "project.name.missing", "Project name is required")
        )

    asset_ids = {asset.id for asset in project.assets}

    track_ids = {track.id for track in project.timeline.tracks}

    clip_ids = {clip.id for track in project.timeline.tracks for clip in track.clips}

    if not project.timeline.tracks:

        report.add_issue(
            ValidationIssue("warning", "timeline.empty", "Timeline has no tracks")
        )

    for track_index, track in enumerate(project.timeline.tracks):

        if track.kind not in {"video", "audio", "subtitle", "effect"}:

            report.add_issue(
                ValidationIssue(
                    "warning",
                    "track.kind.unknown",
                    f"Unknown track kind: {track.kind}",
                    path=f"timeline.tracks[{track_index}]",
                )
            )

        for clip_index, clip in enumerate(track.clips):

            clip_path = f"timeline.tracks[{track_index}].clips[{clip_index}]"

            if clip.start < 0 or clip.end <= clip.start:

                report.add_issue(
                    ValidationIssue(
                        "error",
                        "clip.range.invalid",
                        "Clip start/end range is invalid",
                        path=clip_path,
                        details={"start": clip.start, "end": clip.end},
                    )
                )

            if clip.asset_id not in asset_ids:

                report.add_issue(
                    ValidationIssue(
                        "error",
                        "clip.asset.missing",
                        f"Missing asset reference: {clip.asset_id}",
                        path=clip_path,
                    )
                )

    for stem_index, stem in enumerate(project.audio_stems):

        if stem.track_id and stem.track_id not in track_ids:

            report.add_issue(
                ValidationIssue(
                    "error",
                    "audio_stem.track.missing",
                    f"Missing track reference for audio stem: {stem.track_id}",
                    path=f"audio_stems[{stem_index}]",
                )
            )

    for effect_index, effect in enumerate(project.effects):

        if effect.target_id not in clip_ids and effect.target_id not in track_ids:

            report.add_issue(
                ValidationIssue(
                    "error",
                    "effect.target.missing",
                    f"Missing effect target: {effect.target_id}",
                    path=f"effects[{effect_index}]",
                )
            )

    for subtitle_index, cue in enumerate(project.subtitles):

        cue_path = f"subtitles[{subtitle_index}]"

        if cue.start < 0 or cue.end <= cue.start:

            report.add_issue(
                ValidationIssue(
                    "error",
                    "subtitle.range.invalid",
                    "Subtitle cue start/end range is invalid",
                    path=cue_path,
                    details={"cue_id": cue.id, "start": cue.start, "end": cue.end},
                )
            )

        if cue.spans:

            combined_text = "".join(span.text for span in cue.spans)

            if cue.text != combined_text:

                report.add_issue(
                    ValidationIssue(
                        "error",
                        "subtitle.spans.text_mismatch",
                        "Subtitle cue text must match the concatenated span text",
                        path=f"subtitles[{subtitle_index}]",
                        details={
                            "cue_id": cue.id,
                            "text": cue.text,
                            "combined_span_text": combined_text,
                        },
                    )
                )

    # ID uniqueness checks

    all_asset_ids = [asset.id for asset in project.assets]

    for dup_id in {i for i in all_asset_ids if all_asset_ids.count(i) > 1}:

        report.add_issue(
            ValidationIssue("error", "asset.id.duplicate", f"Duplicate asset id: {dup_id}")
        )

    all_clip_ids = [clip.id for track in project.timeline.tracks for clip in track.clips]

    for dup_id in {i for i in all_clip_ids if all_clip_ids.count(i) > 1}:

        report.add_issue(
            ValidationIssue("error", "clip.id.duplicate", f"Duplicate clip id: {dup_id}")
        )

    all_subtitle_ids = [cue.id for cue in project.subtitles]

    for dup_id in {i for i in all_subtitle_ids if all_subtitle_ids.count(i) > 1}:

        report.add_issue(
            ValidationIssue("error", "subtitle.id.duplicate", f"Duplicate subtitle id: {dup_id}")
        )

    return report


def can_render(project: Project) -> bool:

    return validate_project(project).passed
