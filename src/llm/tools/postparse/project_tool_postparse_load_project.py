from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseLoadProjectMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def load_project(self, project_path: str) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="project.loaded",
            message="Project loaded",
            operation="load_project",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed,
                blockers=[issue.code for issue in report.errors],
            ),
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "subtitle_source_present": bool(project.subtitles),
                "audio_track_present": any(
                    item.kind == "audio" and item.clips
                    for item in project.timeline.tracks
                ),
                **self._project_counts(project),
            },
            payload=self._project_detail_payload(project, project_path),
            summary=f"Loaded project {project.name}",
        ).to_dict()
