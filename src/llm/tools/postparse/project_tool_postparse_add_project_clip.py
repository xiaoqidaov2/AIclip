from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseAddProjectClipMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def add_project_clip(
        self,
        project_path: str,
        clip_id: str,
        asset_id: str,
        start: float,
        end: float,
        track_id: str,
        source_in: float = 0.0,
        source_out: Optional[float] = None,
        speed: float = 1.0,
        track_kind: str = "video",
        track_name: str = "",
        transform: Optional[Dict[str, Any]] = None,
        insert_index: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)

            if failure:

                return failure

            command = AddClipCommand(
                clip=Clip(
                    id=clip_id,
                    asset_id=asset_id,
                    start=float(start),
                    end=float(end),
                    source_in=float(source_in),
                    source_out=float(source_out) if source_out is not None else None,
                    speed=float(speed),
                    transform=dict(transform or {}),
                ),
                track_id=track_id,
                track_kind=track_kind,
                track_name=track_name,
                insert_index=insert_index,
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="add_project_clip",
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
                code="clip.added",
                message="Clip added to timeline",
                operation="add_project_clip",
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
                    "clip_id": clip_id,
                    "asset_id": asset_id,
                },
                payload=self._project_delta_payload(project, project_path, include_tracks=True),
                summary=f"Added clip {clip_id} to track {track_id}",
            ).to_dict()
