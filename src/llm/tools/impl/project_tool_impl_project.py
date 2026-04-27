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
        asset = project.find_asset(clip.asset_id)
        return {
            "clip_id": clip.id,
            "track_id": track.id,
            "track_kind": track.kind,
            "track_name": track.name,
            "asset_id": clip.asset_id,
            "asset_path": asset.path if asset is not None else None,
            "asset_media_type": asset.media_type if asset is not None else None,
            "start": float(clip.start),
            "end": float(clip.end),
            "duration": float(clip.end - clip.start),
            "source_in": float(clip.source_in),
            "source_out": (
                float(clip.source_out) if clip.source_out is not None else None
            ),
            "speed": float(clip.speed),
            "transform": dict(clip.transform or {}),
            "metadata": dict(clip.metadata or {}),
        }

    def _subtitle_search_entry(self, cue: SubtitleCue) -> Dict[str, Any]:
        return {
            "subtitle_id": cue.id,
            "start": float(cue.start),
            "end": float(cue.end),
            "duration": float(cue.end - cue.start),
            "text": cue.text,
            "speaker": cue.speaker,
            "language": cue.language,
            "track_id": cue.track_id,
            "position": cue.position,
            "span_count": len(cue.spans),
        }
