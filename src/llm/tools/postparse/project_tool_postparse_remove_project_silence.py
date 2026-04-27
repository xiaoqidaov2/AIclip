from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseRemoveProjectSilenceMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def remove_project_silence(
        self,
        project_path: str,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
        padding: float = 0.12,
    ) -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure
        if not project.subtitles:
            return ToolResult(
                ok=False,
                status="error",
                code="subtitle.source.missing",
                message="No subtitle source available for silence removal",
                operation="remove_project_silence",
                project_id=project.id,
                project_version=project.version,
                validation=ValidationSnapshot(
                    passed=False, errors=["No subtitle cues available"]
                ),
                render_state=RenderState(
                    ready=False, blockers=["subtitle.source.missing"]
                ),
                state={
                    "project_path": str(Path(project_path)),
                    "subtitle_source_present": False,
                },
                summary="No subtitle cues available",
                error="No subtitle cues available",
            ).to_dict()

        track = self._project_main_track(project, track_id)
        if track is None or not track.clips:
            return self._failure(
                "remove_project_silence",
                "No timeline track available for silence removal",
                code="timeline.track.missing",
                path=str(Path(project_path)),
            )

        source_duration = self._project_source_duration(project, project_path)
        if source_duration is None:
            source_duration = max(
                (
                    float(item.end)
                    for track_item in project.timeline.tracks
                    for item in track_item.clips
                ),
                default=0.0,
            )

        speech_intervals = self._speech_intervals_from_subtitles(project, source_duration, padding)
        if not speech_intervals:
            return self._failure(
                "remove_project_silence",
                "No usable speech intervals were found in subtitles",
                code="subtitle.intervals.missing",
                path=str(Path(project_path)),
            )

        rebuild_tracks = [
            item
            for item in project.timeline.tracks
            if item.kind in {"video", "audio"} and item.clips
        ]
        if not rebuild_tracks:
            rebuild_tracks = [track]
        new_clips_by_track, output_cursor = self._rebuild_tracks_for_silence(project, rebuild_tracks, speech_intervals)
        remapped_subtitles = self._remap_subtitles_after_silence(project, speech_intervals)
        for rebuild_track in rebuild_tracks:
            rebuild_track.clips = new_clips_by_track.get(rebuild_track.id, [])
        project.subtitles = remapped_subtitles
        project.timeline.duration = output_cursor
        project.metadata["subtitle_source_present"] = bool(project.subtitles)
        project.metadata["audio_track_present"] = any(
            item.kind == "audio" and item.clips for item in project.timeline.tracks
        )
        self._apply_auto_style_to_subtitles(project)
        project.bump_version()
        saved_path = self.store.save(project, output_path or project_path)
        report = self.store.validate(project)
        return self._removed_silence_response(project, report, saved_path, track, new_clips_by_track, output_cursor)
