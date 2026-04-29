from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from src.editor_core.project import Clip, Project, SubtitleCue, Track
from src.editor_core.store import ProjectStore


class ProjectToolProjectMixin:
    store: ProjectStore

    def __init__(self) -> None:
        self.store = ProjectStore()
        self._opencc_converter = None
        self._opencc_checked = False

    def _project_counts(self, project: Project) -> Dict[str, Any]:
        return {
            "asset_count": len(project.assets),
            "track_count": len(project.timeline.tracks),
            "subtitle_count": len(project.subtitles),
            "audio_stem_count": len(project.audio_stems),
            "effect_count": len(project.effects),
            "comment_count": len(project.comments),
            "export_preset_count": len(project.export_presets),
        }

    def _project_delta_payload(
        self, project: Project, project_path: str, *,
        include_tracks: bool = False,
        include_short_video: bool = False,
    ) -> Dict[str, Any]:
        """Compact payload — only essential project state that may have changed.

        Use this instead of ``_project_summary_payload`` for most tool
        responses so the LLM receives a smaller, focused delta instead of
        a full project snapshot on every call.
        """
        payload: Dict[str, Any] = {
            "project_id": project.id,
            "project_version": project.version,
            "timeline_duration": float(project.timeline.duration or 0.0),
            "timeline_fps": (
                float(project.timeline.fps or 0.0) if project.timeline.fps else None
            ),
            **self._project_counts(project),
        }
        if include_tracks:
            payload["tracks"] = [
                {"id": t.id, "kind": t.kind, "clip_count": len(t.clips)}
                for t in project.timeline.tracks
            ]
        if include_short_video:
            metrics_builder = getattr(self, "_project_short_video_metrics", None)
            if callable(metrics_builder):
                payload["short_video"] = metrics_builder(project)
        return payload

    def _project_summary_payload(
        self, project: Project, project_path: str
    ) -> Dict[str, Any]:
        track_summaries = []
        for track in project.timeline.tracks:
            track_summaries.append(
                {
                    "id": track.id,
                    "kind": track.kind,
                    "name": track.name,
                    "clip_count": len(track.clips),
                    "visible": track.visible,
                    "locked": track.locked,
                    "muted": track.muted,
                }
            )
        subtitle_languages = sorted(
            {cue.language for cue in project.subtitles if cue.language}
        )
        short_video_metrics = dict(project.metadata.get("short_video_metrics") or {})
        metrics_builder = getattr(self, "_project_short_video_metrics", None)
        if callable(metrics_builder):
            short_video_metrics = metrics_builder(project)
        return {
            "project_path": str(Path(project_path)),
            "project_id": project.id,
            "project_name": project.name,
            "project_version": project.version,
            "timeline_duration": float(project.timeline.duration or 0.0),
            "timeline_fps": (
                float(project.timeline.fps or 0.0) if project.timeline.fps else None
            ),
            "tracks": track_summaries,
            "subtitle_languages": subtitle_languages,
            "has_subtitles": bool(project.subtitles),
            "has_audio_track": any(
                item.kind == "audio" and item.clips for item in project.timeline.tracks
            ),
            "source_media_path": project.metadata.get("source_media_path"),
            "short_video": short_video_metrics,
            **self._project_counts(project),
        }

    def _clip_listing_entry(
        self, project: Project, track: Track, clip: Clip
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "id": clip.id,
            "track_id": track.id,
            "asset_id": clip.asset_id,
            "start": round(float(clip.start), 3),
            "end": round(float(clip.end), 3),
        }
        if clip.source_in:
            entry["source_in"] = round(float(clip.source_in), 3)
        if clip.source_out is not None:
            entry["source_out"] = round(float(clip.source_out), 3)
        if clip.speed != 1.0:
            entry["speed"] = float(clip.speed)
        if clip.transform:
            entry["transform"] = dict(clip.transform)
        return entry

    def _subtitle_search_entry(self, cue: SubtitleCue) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "id": cue.id,
            "start": round(float(cue.start), 3),
            "end": round(float(cue.end), 3),
            "text": cue.text,
        }
        if cue.speaker:
            entry["speaker"] = cue.speaker
        if cue.language:
            entry["language"] = cue.language
        if cue.spans:
            entry["span_count"] = len(cue.spans)
        return entry

    def _compact_subtitle_entry(self, cue: SubtitleCue) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "id": cue.id,
            "start": round(float(cue.start), 3),
            "end": round(float(cue.end), 3),
            "text": cue.text,
        }
        if cue.speaker:
            entry["speaker"] = cue.speaker
        if cue.language:
            entry["language"] = cue.language
        return entry

    def _project_detail_payload(
        self, project: Project, project_path: str
    ) -> Dict[str, Any]:
        summary = self._project_summary_payload(project, project_path)
        summary["clips"] = [
            self._clip_listing_entry(project, track, clip)
            for track in project.timeline.tracks
            for clip in track.clips
        ]
        summary["subtitles"] = [
            self._compact_subtitle_entry(cue) for cue in project.subtitles
        ]
        return summary
