from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseCreateHelpersMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _existing_project_response(
        self,
        existing_project: Project,
        existing_project_path: Path,
        source_path: Path,
    ) -> Dict[str, Any]:
        migrated = self.store.normalize_project_asset_paths(
            existing_project, existing_project_path
        )
        if migrated:
            existing_project.bump_version()
            existing_project_path = self.store.save(existing_project, existing_project_path)
        report = self.store.validate(existing_project)
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.reused",
            message="Existing project loaded for media path",
            operation="create_project_from_media",
            project_id=existing_project.id,
            project_version=existing_project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed, blockers=[issue.code for issue in report.errors]
            ),
            artifacts=[
                ArtifactRef(type="project", path=str(existing_project_path)),
                ArtifactRef(type="media", path=str(source_path)),
            ],
            state={
                "project_path": str(existing_project_path),
                "media_path": str(source_path),
                "reused_existing_project": True,
                **self._project_counts(existing_project),
            },
            payload=self._project_delta_payload(existing_project, str(existing_project_path), include_tracks=True, include_short_video=True),
            summary=f"Reused existing project {existing_project.name}",
        ).to_dict()

    def _build_project_from_media(
        self,
        source_path: Path,
        media_info: Dict[str, Any],
        project_name: Optional[str],
        project_id: Optional[str],
        asset_id: Optional[str],
        track_id: str,
        clip_id: str,
    ) -> Project:
        asset = Asset(
            id=asset_id or source_path.stem,
            path=str(source_path),
            source="local",
            media_type=media_info.get("media_kind", "video"),
            duration=media_info["duration"] or None,
            metadata={
                "source_media_path": str(source_path),
                "has_audio": media_info["has_audio"],
                "fps": media_info["fps"],
                "size": media_info["size"],
                "media_kind": media_info.get("media_kind", "video"),
            },
        )
        clip_duration = media_info["duration"] if media_info["duration"] > 0 else 0.0
        track_kind = media_info.get("media_kind", "video")
        tracks = [
            Track(
                id=track_id,
                kind=track_kind,
                name="Main Audio" if track_kind == "audio" else "Main Video",
                clips=[
                    Clip(
                        id=clip_id,
                        asset_id=asset.id,
                        start=0.0,
                        end=clip_duration,
                        source_in=0.0,
                        source_out=clip_duration,
                    )
                ],
            )
        ]
        if track_kind == "video" and media_info["has_audio"]:
            tracks.append(
                Track(
                    id="audio_1",
                    kind="audio",
                    name="Main Audio",
                    role="dialogue",
                    volume=1.0,
                    clips=[
                        Clip(
                            id=f"{clip_id}_audio",
                            asset_id=asset.id,
                            start=0.0,
                            end=clip_duration,
                            source_in=0.0,
                            source_out=clip_duration,
                        )
                    ],
                )
            )
        project = Project(
            id=project_id or source_path.stem,
            name=project_name or source_path.stem,
            assets=[asset],
            timeline=Timeline(
                duration=clip_duration,
                fps=media_info["fps"] or None,
                tracks=tracks,
            ),
            metadata={
                "source_media_path": str(source_path),
                "source_media_name": source_path.name,
                "source_media_duration": media_info["duration"],
                "source_media_fps": media_info["fps"],
                "source_media_has_audio": media_info["has_audio"],
                "source_media_kind": media_info.get("media_kind", "video"),
                "subtitle_source_present": False,
                "analysis_scope": "project_core",
            },
        )
        if track_kind == "video":
            project.metadata["auto_style_profile"] = "dynamic_subtitles_v1"
        return project

    def _created_project_response(
        self,
        project: Project,
        report: Any,
        saved_path: Path,
        source_path: Path,
        media_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.created",
            message="Project created from media",
            operation="create_project_from_media",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed, blockers=[issue.code for issue in report.errors]
            ),
            artifacts=[
                ArtifactRef(type="project", path=str(saved_path)),
                ArtifactRef(type="media", path=str(source_path)),
            ],
            state={
                "project_path": str(saved_path),
                "media_path": str(source_path),
                "subtitle_source_present": False,
                "audio_track_present": media_info["has_audio"],
                **self._project_counts(project),
            },
            payload=self._project_delta_payload(project, str(saved_path), include_tracks=True, include_short_video=True),
            summary=f"Created project for {source_path.name}",
        ).to_dict()
