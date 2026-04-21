from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParsePrepareProjectRenderMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def prepare_project_render(
        self,
        project_path: str,
        preview_path: Optional[str] = None,
        final_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        report = self.store.validate(project)

        render_ready = report.passed

        render_state = RenderState(
            ready=render_ready,
            blockers=[issue.code for issue in report.errors],
            preview_path=preview_path,
            final_path=final_path,
        )

        return ToolResult(
            ok=render_ready,
            status="ok" if render_ready else "warn",
            code="render.plan.ready" if render_ready else "render.plan.blocked",
            message="Render plan prepared" if render_ready else "Render plan blocked",
            operation="prepare_project_render",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=render_state,
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "preview_path": preview_path,
                "final_path": final_path,
            },
            payload=project.to_dict(),
            next_actions=(
                ["fix_project", "revalidate"] if not render_ready else ["render_final"]
            ),
            summary=(
                "Render plan prepared"
                if render_ready
                else "Render blocked by validation errors"
            ),
        ).to_dict()
