from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSaveProjectMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def save_project(
        self,
        project_path: str,
        output_path: Optional[str] = None,
        format: Optional[str] = None,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        target_path = Path(output_path or project_path)

        try:

            saved_path = self.store.save(project, target_path, format=format)  # type: ignore[arg-type]

        except Exception as exc:

            return self._failure(
                "save_project",
                f"Failed to save project: {exc}",
                code="project.save_failed",
                path=str(target_path),
            )

        report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.saved",
            message="Project saved",
            operation="save_project",
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
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={
                "project_path": str(saved_path),
                "format": format or saved_path.suffix.lstrip("."),
            },
            payload=project.to_dict(),
            summary=f"Saved project to {saved_path}",
        ).to_dict()
