from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseLockProjectCommentMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def lock_project_comment(
        self,
        project_path: str,
        comment_id: str,
        locked: bool = True,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)

            if failure:

                return failure

            command = LockCommentCommand(comment_id, locked=locked)

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="lock_project_comment",
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
                code="comment.locked" if locked else "comment.unlocked",
                message="Comment lock updated",
                operation="lock_project_comment",
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
                summary=f"{'Locked' if locked else 'Unlocked'} comment {comment_id}",
            ).to_dict()
