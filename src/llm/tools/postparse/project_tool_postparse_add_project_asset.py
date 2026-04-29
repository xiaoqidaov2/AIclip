from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseAddProjectAssetMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def add_project_asset(
        self,
        project_path: str,
        asset_id: str,
        asset_path: str,
        media_type: str = "unknown",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)

            if failure:

                return failure

            normalized_asset_path = asset_path

            asset_source = "local" if Path(asset_path).is_absolute() else "net_asset"

            if Path(asset_path).is_absolute():

                try:

                    normalized_asset_path = self.store.import_asset_to_project(
                        asset_path,
                        project_path,
                        preferred_name=Path(asset_path).name,
                    )

                except Exception as exc:

                    return self._failure(
                        "add_project_asset",
                        f"Failed to import asset into project workspace: {exc}",
                        code="asset.import_failed",
                        path=str(Path(project_path).resolve().parent / "media"),
                    )

            command = AddAssetCommand(
                Asset(
                    id=asset_id,
                    path=normalized_asset_path,
                    source=asset_source,
                    media_type=media_type,
                )
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="add_project_asset",
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

            asset = project.find_asset(asset_id)
            if asset is not None:
                asset.path = normalized_asset_path
                asset.source = asset_source

            saved_path = self.store.save(project, output_path or project_path)

            report = self.store.validate(project)

            return ToolResult(
                ok=report.passed,
                status="ok" if report.passed else "warn",
                code="asset.added",
                message="Asset added",
                operation="add_project_asset",
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
                summary=f"Added asset {asset_id}",
            ).to_dict()
