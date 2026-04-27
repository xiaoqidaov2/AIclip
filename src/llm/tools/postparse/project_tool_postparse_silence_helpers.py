from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSilenceHelpersMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _speech_intervals_from_subtitles(self, project: Project, source_duration: float, padding: float) -> list[tuple[float, float]]:
        intervals: list[tuple[float, float]] = []
        effective_padding = max(0.0, float(padding))
        min_gap = max(0.06, effective_padding * 0.5)
        for cue in sorted(project.subtitles, key=lambda item: (item.start, item.end)):
            start = max(0.0, min(float(cue.start) - effective_padding, source_duration))
            end = max(
                start,
                min(float(cue.end) + effective_padding, source_duration),
            )
            if end <= start:
                continue
            if intervals and start - intervals[-1][1] < min_gap:
                prev_start, prev_end = intervals[-1]
                intervals[-1] = (prev_start, max(prev_end, end))
            else:
                intervals.append((start, end))
        return self._merge_intervals(intervals)

    def _rebuild_tracks_for_silence(self, project: Project, rebuild_tracks: list[Track], speech_intervals: list[tuple[float, float]]) -> tuple[dict[str, list[Clip]], float]:
        new_clips_by_track: dict[str, list[Clip]] = {}
        output_cursor = 0.0
        for rebuild_track in rebuild_tracks:
            source_clip = rebuild_track.clips[0]
            rebuilt_clips: list[Clip] = []
            track_cursor = 0.0
            for index, (start, end) in enumerate(speech_intervals, start=1):
                segment_duration = max(0.0, end - start)
                if segment_duration <= 0:
                    continue
                rebuilt_clips.append(Clip(id=f"{source_clip.id}_{rebuild_track.id}_seg_{index:03d}", asset_id=source_clip.asset_id, start=track_cursor, end=track_cursor + segment_duration, source_in=start, source_out=end, speed=source_clip.speed, transform=dict(source_clip.transform), metadata={**dict(source_clip.metadata), "source_segment_index": index, "track_id": rebuild_track.id}))
                track_cursor += segment_duration
            new_clips_by_track[rebuild_track.id] = rebuilt_clips
            output_cursor = max(output_cursor, track_cursor)
        return new_clips_by_track, output_cursor

    def _remap_subtitles_after_silence(self, project: Project, speech_intervals: list[tuple[float, float]]) -> list[SubtitleCue]:
        remapped: list[SubtitleCue] = []
        for cue in sorted(project.subtitles, key=lambda item: (item.start, item.end)):
            new_start = self._remap_time(cue.start, speech_intervals)
            new_end = self._remap_time(cue.end, speech_intervals)
            if new_end <= new_start:
                continue
            remapped.append(SubtitleCue(id=cue.id, start=new_start, end=new_end, text=cue.text, spans=[SubtitleSpan.from_dict(span.to_dict() if hasattr(span, "to_dict") else dict(span)) if isinstance(span, dict) else (SubtitleSpan.from_dict(span.__dict__) if hasattr(span, "__dict__") else span) for span in cue.spans], effects=[SubtitleEffect.from_dict(effect.to_dict() if hasattr(effect, "to_dict") else dict(effect)) if isinstance(effect, dict) else (SubtitleEffect.from_dict(effect.__dict__) if hasattr(effect, "__dict__") else effect) for effect in cue.effects], track_id=cue.track_id, speaker=cue.speaker, language=cue.language, position=cue.position, margin_top=cue.margin_top, margin_bottom=cue.margin_bottom, margin_left=cue.margin_left, margin_right=cue.margin_right, offset_y=cue.offset_y, font_size=cue.font_size, font_path=cue.font_path, metadata=dict(cue.metadata)))
        return remapped

    def _removed_silence_response(self, project: Project, report: Any, saved_path: Path, track: Track, new_clips_by_track: dict[str, list[Clip]], output_cursor: float) -> Dict[str, Any]:
        segment_count = len(next(iter(new_clips_by_track.values()), []))
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="timeline.silence.removed",
            message="Silence removed from timeline",
            operation="remove_project_silence",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(passed=report.passed, warnings=[issue.message for issue in report.warnings], errors=[issue.message for issue in report.errors]),
            render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors]),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={"project_path": str(saved_path), "track_id": track.id, "subtitle_source_present": bool(project.subtitles), "audio_track_present": any(item.kind == "audio" and item.clips for item in project.timeline.tracks), "subtitle_count": len(project.subtitles), "segment_count": segment_count, "timeline_duration": output_cursor},
            payload=project.to_dict(),
            next_actions=["prepare_project_render"],
            summary=f"Removed silence with {segment_count} retained segments",
        ).to_dict()
