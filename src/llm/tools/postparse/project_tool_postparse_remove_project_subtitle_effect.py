from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseRemoveProjectSubtitleEffectMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def remove_project_subtitle_effect(
        self,
        project_path: str,
        subtitle_id: str,
        kind: Optional[str] = None,
        output_path: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Remove one or all effects from a subtitle cue.







        Pass *kind* to remove only effects of that type, or omit it to clear all effects.



        """

        with self.store.project_lock(project_path):

            project, failure = self._load(project_path)

            if failure:

                return failure

            command = RemoveSubtitleEffectCommand(
                cue_id=subtitle_id, kind=kind, span_id=span_id
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="remove_project_subtitle_effect",
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

            saved_path = self.store.save(
                project, output_path or project_path, _already_locked=True
            )

            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.effect.removed",
            message=f"Effect(s) removed from subtitle {subtitle_id}",
            operation="remove_project_subtitle_effect",
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
                "subtitle_id": subtitle_id,
            },
            payload=project.to_dict(),
            summary=f"Removed subtitle effect(s) from cue {subtitle_id}",
        ).to_dict()
