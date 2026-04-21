from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSetProjectClipSpeedMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def set_project_clip_speed(
        self,
        project_path: str,
        clip_id: str,
        speed: float,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        command = SetClipSpeedCommand(clip_id=clip_id, speed=speed, track_id=track_id)

        result = command.execute(project)

        if not result.ok:

            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="set_project_clip_speed",
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
            code="clip.speed.updated",
            message="Clip speed updated",
            operation="set_project_clip_speed",
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
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Updated speed for clip {clip_id}",
        ).to_dict()
