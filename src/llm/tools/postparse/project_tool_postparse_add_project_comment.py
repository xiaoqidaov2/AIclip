from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseAddProjectCommentMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def add_project_comment(
        self,
        project_path: str,
        comment_id: str,
        author: str,
        text: str,
        anchor: Optional[str] = None,
        timecode: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        command = AddCommentCommand(
            Comment(
                id=comment_id,
                author=author,
                text=text,
                anchor=anchor,
                timecode=timecode,
            )
        )

        result = command.execute(project)

        if not result.ok:

            return ToolResult(
                ok=False,
                status="error",
                code=result.code,
                message=result.message,
                operation="add_project_comment",
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
            code="comment.added",
            message="Comment added",
            operation="add_project_comment",
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
            summary=f"Added comment {comment_id}",
        ).to_dict()
