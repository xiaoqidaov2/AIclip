from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParsePlanProjectExportMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def plan_project_export(
        self,
        project_path: str,
        preset_id: str,
        output_dir: str,
        base_name: Optional[str] = None,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        preset = next(
            (item for item in project.export_presets if item.id == preset_id), None
        )

        if preset is None:

            return self._failure(
                "plan_project_export",
                f"Export preset not found: {preset_id}",
                code="export_preset.not_found",
                path=str(Path(project_path)),
            )

        report = self.store.validate(project)

        safe_name = base_name or project.name or project.id

        export_dir = Path(output_dir)

        preview_path = export_dir / f"{safe_name}_preview.{preset.format}"

        final_path = export_dir / f"{safe_name}_final.{preset.format}"

        sidecar_path = export_dir / f"{safe_name}.json"

        render_ready = report.passed

        blockers = [issue.code for issue in report.errors]

        return ToolResult(
            ok=render_ready,
            status="ok" if render_ready else "warn",
            code="export.plan.ready" if render_ready else "export.plan.blocked",
            message="Export plan prepared" if render_ready else "Export plan blocked",
            operation="plan_project_export",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=render_ready,
                blockers=blockers,
                preview_path=str(preview_path),
                final_path=str(final_path),
            ),
            artifacts=[
                ArtifactRef(type="project", path=str(Path(project_path))),
                ArtifactRef(type="planned_preview", path=str(preview_path)),
                ArtifactRef(type="planned_final", path=str(final_path)),
                ArtifactRef(type="planned_sidecar", path=str(sidecar_path)),
            ],
            state={
                "project_path": str(Path(project_path)),
                "preset_id": preset.id,
                "preset_format": preset.format,
                "output_dir": str(export_dir),
                "preview_path": str(preview_path),
                "final_path": str(final_path),
                "sidecar_path": str(sidecar_path),
            },
            payload=project.to_dict(),
            next_actions=(
                ["fix_project", "revalidate"]
                if not render_ready
                else ["render_preview", "render_final"]
            ),
            summary=f"Planned export with preset {preset_id}",
        ).to_dict()
