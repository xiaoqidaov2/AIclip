from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseGetProjectSummaryMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def get_project_summary(self, project_path: str) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        report = self.store.validate(project)

        payload = self._project_summary_payload(project, project_path)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.summary.ready",
            message="Project summary ready",
            operation="get_project_summary",
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
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "timeline_duration": payload["timeline_duration"],
                **self._project_counts(project),
            },
            payload=payload,
            summary=f"Prepared summary for project {project.name}",
        ).to_dict()
