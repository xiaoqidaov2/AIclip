from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseUpdateProjectAudioStemMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def update_project_audio_stem(
        self,
        project_path: str,
        stem_id: str,
        role: Optional[str] = None,
        asset_path: Optional[str] = None,
        track_id: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)

            if failure:

                return failure

            command = UpdateAudioStemCommand(
                stem_id=stem_id,
                role=role,
                path=asset_path,
                track_id=track_id,
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="update_project_audio_stem",
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
                code="audio_stem.updated",
                message="Audio stem updated",
                operation="update_project_audio_stem",
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
                payload=self._project_delta_payload(project, project_path),
                summary=f"Updated audio stem {stem_id}",
            ).to_dict()
