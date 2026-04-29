from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseApplyOverlayToScreenMixin:
    _DEFAULT_OVERLAY_MAX_TARGET_RATIO = 0.35

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _clip_asset_size(self, project: Project, clip: Clip) -> tuple[Optional[float], Optional[float]]:
        asset = project.find_asset(clip.asset_id)
        size = asset.metadata.get("size") if asset is not None else None
        width = float(size[0]) if isinstance(size, list) and len(size) >= 1 and float(size[0]) > 0 else None
        height = float(size[1]) if isinstance(size, list) and len(size) >= 2 and float(size[1]) > 0 else None
        return width, height

    def _overlay_default_scale(
        self,
        project: Project,
        asset: Asset,
        target_clip: Clip,
        base_width: Optional[float],
        base_height: Optional[float],
    ) -> float:
        if not bool(asset.metadata.get("transparent")):
            return 1.0
        if not base_width or not base_height:
            return 1.0
        target_width, target_height = self._clip_asset_size(project, target_clip)
        if not target_width or not target_height:
            size = project.metadata.get("source_media_size") or project.metadata.get("size")
            target_width = float(size[0]) if isinstance(size, list) and len(size) >= 1 and float(size[0]) > 0 else None
            target_height = float(size[1]) if isinstance(size, list) and len(size) >= 2 and float(size[1]) > 0 else None
        if not target_width or not target_height:
            return 1.0
        max_width = float(target_width) * self._DEFAULT_OVERLAY_MAX_TARGET_RATIO
        max_height = float(target_height) * self._DEFAULT_OVERLAY_MAX_TARGET_RATIO
        return min(1.0, max_width / float(base_width), max_height / float(base_height))

    def _normalize_overlay_position(
        self,
        project: Project,
        x: float,
        y: float,
        overlay_width: Optional[float],
        overlay_height: Optional[float],
    ) -> tuple[int, int]:
        """Convert overlay position to absolute pixel coordinates.

        Supports two conventions:
        - Normalized ratios (0.0-1.0): interpreted as anchor point on the
          canvas; the overlay is centered on that point.
        - Absolute pixels (integers or floats > 1.0): interpreted as top-left
          corner of the overlay (MoviePy with_position semantics).
        """
        canvas_size = project.metadata.get("source_media_size") or project.metadata.get("size")
        if isinstance(canvas_size, list) and len(canvas_size) >= 2:
            canvas_w = float(canvas_size[0])
            canvas_h = float(canvas_size[1])
        else:
            first_asset = project.assets[0] if project.assets else None
            asset_size = first_asset.metadata.get("size") if first_asset else None
            if isinstance(asset_size, list) and len(asset_size) >= 2:
                canvas_w = float(asset_size[0])
                canvas_h = float(asset_size[1])
            else:
                canvas_w, canvas_h = 1080.0, 1920.0

        def _is_normalized(v: float) -> bool:
            # Exact integers (e.g. x=1, x=120) are absolute pixels, never normalized.
            if type(v) is int:
                return False
            fv = float(v)
            if fv > 1.0:
                return False
            return 0.0 <= fv <= 1.0

        is_norm_x = _is_normalized(x)
        is_norm_y = _is_normalized(y)

        if is_norm_x:
            # Center overlay on the normalized anchor point.
            abs_x = float(x) * canvas_w
            ow = float(overlay_width) if overlay_width is not None else 0.0
            final_x = int(abs_x - ow / 2)
            # Clamp so the overlay stays fully within canvas bounds.
            # When size is unknown (ow == 0) fall back to top-left at anchor.
            if ow > 0:
                final_x = max(0, min(final_x, int(canvas_w - ow)))
            else:
                final_x = max(0, min(final_x, int(canvas_w)))
        else:
            # Absolute pixel: top-left corner (MoviePy semantics).
            final_x = int(float(x))

        if is_norm_y:
            abs_y = float(y) * canvas_h
            oh = float(overlay_height) if overlay_height is not None else 0.0
            final_y = int(abs_y - oh / 2)
            if oh > 0:
                final_y = max(0, min(final_y, int(canvas_h - oh)))
            else:
                final_y = max(0, min(final_y, int(canvas_h)))
        else:
            final_y = int(float(y))

        return final_x, final_y

    def _compute_overlay_y_below_subtitles(
        self,
        project: Project,
        target_clip: Clip,
        overlay_height: Optional[float],
    ) -> float:
        """Compute a Y coordinate (absolute pixels, top-left) that places the overlay
        directly below any subtitles overlapping the target clip time range.
        """
        canvas_size = project.metadata.get("source_media_size") or project.metadata.get("size")
        if isinstance(canvas_size, list) and len(canvas_size) >= 2:
            video_height = float(canvas_size[1])
        else:
            first_asset = project.assets[0] if project.assets else None
            asset_size = first_asset.metadata.get("size") if first_asset else None
            if isinstance(asset_size, list) and len(asset_size) >= 2:
                video_height = float(asset_size[1])
            else:
                video_height = 1920.0

        oh = float(overlay_height) if overlay_height is not None else 0.0
        bottom_margin = max(24, int(video_height * 0.06))

        overlapping = [
            cue for cue in project.subtitles
            if cue.start < target_clip.end and cue.end > target_clip.start
        ]

        if not overlapping:
            return max(0.0, video_height - oh - bottom_margin)

        max_subtitle_bottom = 0.0
        for cue in overlapping:
            font_size = cue.font_size or 24
            line_count = max(1, (cue.text or "").count("\n") + 1)
            subtitle_height = font_size * line_count * 1.5
            subtitle_top = self._subtitle_y_position(cue, int(subtitle_height), int(video_height), project=project)
            subtitle_bottom = subtitle_top + subtitle_height
            if subtitle_bottom > max_subtitle_bottom:
                max_subtitle_bottom = subtitle_bottom

        target_y = max_subtitle_bottom + 20.0
        if oh > 0:
            target_y = min(target_y, video_height - oh)
        return max(0.0, target_y)

    def apply_overlay_to_screen(
        self,
        project_path: str,
        asset_id: str,
        target_clip_id: str,
        overlay_clip_id: str,
        x: float,
        y: float,
        width: Optional[float] = None,
        height: Optional[float] = None,
        start: Optional[float] = None,
        end: Optional[float] = None,
        opacity: float = 1.0,
        track_id: str = "overlay_track",
        track_name: str = "Overlay Track",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            asset = project.find_asset(asset_id)
            if asset is None:
                return self._failure(
                    "apply_overlay_to_screen",
                    f"Asset not found: {asset_id}",
                    code="asset.not_found",
                    path=str(Path(project_path)),
                )

            target_clip = project.find_clip(target_clip_id)
            if target_clip is None:
                return self._failure(
                    "apply_overlay_to_screen",
                    f"Clip not found: {target_clip_id}",
                    code="clip.not_found",
                    path=str(Path(project_path)),
                )

            overlay_start = float(start if start is not None else target_clip.start)
            asset_duration = float(asset.duration or 0.0)
            if end is not None:
                overlay_end = float(end)
            elif asset_duration > 0:
                overlay_end = min(float(target_clip.end), overlay_start + asset_duration)
            else:
                overlay_end = float(target_clip.end)
            if overlay_end <= overlay_start:
                return self._failure(
                    "apply_overlay_to_screen",
                    "Overlay range is invalid",
                    code="clip.range.invalid",
                    path=str(Path(project_path)),
                )

            base_size = asset.metadata.get("size") or []
            base_width = float(base_size[0]) if isinstance(base_size, list) and len(base_size) >= 1 and float(base_size[0]) > 0 else None
            base_height = float(base_size[1]) if isinstance(base_size, list) and len(base_size) >= 2 and float(base_size[1]) > 0 else None
            scale = 1.0
            if width is not None and base_width:
                scale = float(width) / base_width
            elif height is not None and base_height:
                scale = float(height) / base_height
            else:
                scale = self._overlay_default_scale(project, asset, target_clip, base_width, base_height)

            # Compute actual overlay pixel dimensions for centering
            overlay_w = float(width) if width is not None else (float(base_width) * scale if base_width else None)
            overlay_h = float(height) if height is not None else (float(base_height) * scale if base_height else None)

            # Restrict placement: horizontally centered, vertically below subtitles
            x = 0.5
            y = self._compute_overlay_y_below_subtitles(project, target_clip, overlay_h)

            abs_x, abs_y = self._normalize_overlay_position(project, x, y, overlay_w, overlay_h)

            transform = {
                "x": float(abs_x),
                "y": float(abs_y),
                "scale": float(scale),
                "opacity": float(opacity),
            }
            if width is not None:
                transform["width"] = float(width)
            if height is not None:
                transform["height"] = float(height)

            command = AddClipCommand(
                clip=Clip(
                    id=overlay_clip_id,
                    asset_id=asset_id,
                    start=overlay_start,
                    end=overlay_end,
                    transform=transform,
                    metadata={
                        "role": "overlay",
                        "target_clip_id": target_clip_id,
                        "screen_binding": {
                            "x": float(abs_x),
                            "y": float(abs_y),
                            "width": float(width) if width is not None else None,
                            "height": float(height) if height is not None else None,
                        },
                        "placement_defaults": {
                            "start_defaulted_to_target": start is None,
                            "size_auto_capped": width is None and height is None and scale < 1.0,
                        },
                    },
                ),
                track_id=track_id,
                track_kind="video",
                track_name=track_name,
                create_track=True,
            )

            result = command.execute(project)

            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="apply_overlay_to_screen",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(
                        ready=False, blockers=list(result.validation.errors)
                    ),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path)
            report = self.store.validate(project)

            return ToolResult(
                ok=report.passed,
                status="ok" if report.passed else "warn",
                code="overlay.applied",
                message="Overlay clip added to timeline",
                operation="apply_overlay_to_screen",
                project_id=project.id,
                project_version=project.version,
                changes=result.changes,
                validation=ValidationSnapshot(
                    passed=report.passed,
                    warnings=[issue.message for issue in report.warnings],
                    errors=[issue.message for issue in report.errors],
                ),
                render_state=RenderState(
                    ready=report.passed, blockers=[issue.code for issue in report.errors]
                ),
                artifacts=[ArtifactRef(type="project", path=str(saved_path))],
                state={
                    **result.state,
                    "project_path": str(saved_path),
                    "overlay_clip_id": overlay_clip_id,
                    "target_clip_id": target_clip_id,
                    "track_id": track_id,
                },
                payload=self._project_delta_payload(project, project_path),
                next_actions=["render_project"],
                summary=f"Applied overlay {overlay_clip_id} to clip {target_clip_id}",
            ).to_dict()
