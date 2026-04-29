from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from moviepy import CompositeVideoClip, ImageClip  # type: ignore[import-untyped]
from moviepy.video.fx import CrossFadeIn, CrossFadeOut  # type: ignore[import-untyped]
from src.editor_core.contracts import ArtifactRef, RenderState, ToolResult, ValidationSnapshot
from src.editor_core.project import Track


class ProjectToolRenderPipelineMixin:
    store: Any

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def render_project(self, project_path: str, output_path: Optional[str] = None, track_id: Optional[str] = None, font_path: Optional[str] = None, font_size: int = 36, subtitle_color: str = "white") -> Dict[str, Any]:
        project, failure = self._load(project_path)
        if failure:
            return failure
        render_tracks: list[Track] = []
        if track_id:
            selected_track = project.find_track(track_id)
            if selected_track is not None and selected_track.kind == "video" and selected_track.visible and selected_track.clips:
                render_tracks.append(selected_track)
        else:
            render_tracks = [item for item in project.timeline.tracks if item.kind == "video" and item.visible and item.clips]
        if not render_tracks:
            return self._failure("render_project", "No timeline track available for rendering", code="timeline.track.missing", path=str(Path(project_path)))
        composite = None
        base_video = None
        rendered_clips: list[Any] = []
        opened_media: list[Any] = []
        subtitle_layers: list[Any] = []
        try:
            canvas_width, canvas_height, fps = self._project_canvas(project, project_path)
            timeline_duration = max(float(project.timeline.duration or 0.0), max(float(item.end) for track in render_tracks for item in track.clips))
            # Separate base clips from overlay clips for correct z-ordering
            base_clips: list[Any] = []
            overlay_clips: list[Any] = []
            for track in render_tracks:
                for clip in sorted(track.clips, key=lambda item: (item.start, item.end, item.id)):
                    media_clip, opened = self._build_timeline_video_clip(project, clip, project_path)
                    if str((clip.metadata or {}).get("role", "")).lower() == "overlay":
                        overlay_clips.append(media_clip)
                    else:
                        base_clips.append(media_clip)
                    opened_media.extend(opened)
            rendered_clips = base_clips + overlay_clips
            if not rendered_clips:
                return self._failure("render_project", "No renderable clips were found on the timeline", code="timeline.clip.missing", path=str(Path(project_path)))
            base_video = self._set_clip_duration(CompositeVideoClip(rendered_clips, size=(canvas_width, canvas_height)), timeline_duration)
            if project.subtitles:
                for cue in project.subtitles:
                    margin_left = int(cue.margin_left if cue.margin_left is not None else (cue.metadata.get("margin_left") or 20))
                    margin_right = int(cue.margin_right if cue.margin_right is not None else (cue.metadata.get("margin_right") or 20))
                    effective_width = max(100, int(base_video.w) - margin_left - margin_right)
                    cue_font_size = cue.font_size if cue.font_size else font_size
                    cue_font_path = cue.font_path if cue.font_path else font_path
                    image = self._make_subtitle_image(cue.text, effective_width, cue_font_path, cue_font_size, subtitle_color, cue.spans, cue.effects or [])
                    cue_duration = max(0.01, cue.end - cue.start)
                    fx_map = {fx.kind: fx.parameters for fx in (cue.effects or [])}
                    if "typewriter" in fx_map:
                        subtitle_layers.extend(self._make_typewriter_clips(cue, effective_width, cue_font_path, cue_font_size, subtitle_color, fx_map["typewriter"], base_video, project=project))
                        continue
                    subtitle_clip = self._clip_call(self._set_clip_duration(ImageClip(np.array(image)), cue_duration), "with_start", cue.start)
                    subtitle_clip = self._clip_call(subtitle_clip, "with_end", cue.end)
                    y_pos = self._subtitle_y_position(cue, image.height, int(base_video.h), project=project)
                    x_pos = self._subtitle_x_position(cue, image.width, int(base_video.w))
                    subtitle_clip = self._apply_slide_anim(subtitle_clip, fx_map["slide_in"], x_pos, y_pos, cue.start, mode="in") if "slide_in" in fx_map else self._apply_slide_anim(subtitle_clip, fx_map["slide_out"], x_pos, y_pos, cue.end, mode="out") if "slide_out" in fx_map else self._clip_call(subtitle_clip, "with_position", (x_pos, y_pos))
                    if "scale_in" in fx_map:
                        subtitle_clip = self._apply_scale_in(subtitle_clip, fx_map["scale_in"], x_pos, y_pos)
                    fx_list = []
                    if "fade_in" in fx_map:
                        fx_list.append(CrossFadeIn(float(fx_map["fade_in"].get("duration", 0.3))))
                    if "fade_out" in fx_map:
                        fx_list.append(CrossFadeOut(float(fx_map["fade_out"].get("duration", 0.3))))
                    if hasattr(subtitle_clip, "with_effects") and fx_list:
                        subtitle_clip = subtitle_clip.with_effects(fx_list)
                    elif hasattr(subtitle_clip, "crossfadein"):
                        if "fade_in" in fx_map:
                            subtitle_clip = self._clip_call(subtitle_clip, "crossfadein", float(fx_map["fade_in"].get("duration", 0.3)))
                        if "fade_out" in fx_map:
                            subtitle_clip = self._clip_call(subtitle_clip, "crossfadeout", float(fx_map["fade_out"].get("duration", 0.3)))
                    subtitle_layers.append(subtitle_clip)
                composite = CompositeVideoClip([base_video, *subtitle_layers], size=(base_video.w, base_video.h))
            else:
                composite = base_video
            workspace = self.store.workspace_for_project(project_path)
            workspace.ensure()
            target_output = Path(output_path).resolve() if output_path else workspace.default_export_path(project.name)
            Path(target_output).parent.mkdir(parents=True, exist_ok=True)
            render_output = target_output
            temp_output: Optional[Path] = None
            if any(ord(char) > 127 for char in str(target_output)):
                fd, temp_output_str = tempfile.mkstemp(dir=str(target_output.parent), prefix="aiclip_render_", suffix=target_output.suffix or ".mp4")
                os.close(fd)
                temp_output = Path(temp_output_str)
                temp_output.unlink(missing_ok=True)
                render_output = temp_output
            composite.write_videofile(str(render_output), fps=fps, codec="libx264", audio_codec="aac")
            if temp_output is not None:
                os.replace(temp_output, target_output)
        except Exception as exc:
            return self._failure("render_project", f"Failed to render project: {exc}", code="render.failed", path=str(Path(output_path) if output_path else Path(project_path).resolve().parent / "exports"))
        finally:
            for item in subtitle_layers + rendered_clips + opened_media:
                close = getattr(item, "close", None)
                if callable(close):
                    close()
            for item in (base_video, composite):
                close = getattr(item, "close", None) if item is not None else None
                if callable(close):
                    close()
        report = self.store.validate(project)
        return ToolResult(ok=report.passed, status="ok" if report.passed else "warn", code="render.completed", message="Project rendered", operation="render_project", project_id=project.id, project_version=project.version, validation=ValidationSnapshot(passed=report.passed, warnings=[issue.message for issue in report.warnings], errors=[issue.message for issue in report.errors]), render_state=RenderState(ready=report.passed, blockers=[issue.code for issue in report.errors], final_path=str(target_output)), artifacts=[ArtifactRef(type="video", path=str(target_output)), ArtifactRef(type="project", path=str(Path(project_path)))], state={"project_path": str(Path(project_path)), "final_path": str(target_output)}, payload=self._project_summary_payload(project, project_path), summary=f"Rendered project to {target_output}").to_dict()
