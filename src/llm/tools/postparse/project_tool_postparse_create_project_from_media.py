from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseCreateProjectFromMediaMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def create_project_from_media(
        self,
        media_path: str,
        project_path: Optional[str] = None,
        project_name: Optional[str] = None,
        project_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        track_id: str = "video_1",
        clip_id: str = "clip_1",
    ) -> Dict[str, Any]:
        source_path = Path(media_path).resolve()
        if not source_path.exists():
            return self._failure(
                "create_project_from_media",
                f"Media file not found: {media_path}",
                code="media.not_found",
                path=str(source_path),
            )

        if project_path is None:
            existing_project_path = self.store.find_project_for_media(source_path)
            if existing_project_path is not None and existing_project_path.exists():
                existing_project = self.store.load(existing_project_path)
                return self._existing_project_response(existing_project, existing_project_path, source_path)
        try:
            media_info = self._probe_media(source_path)
        except Exception as exc:
            return self._failure(
                "create_project_from_media",
                f"Failed to inspect media: {exc}",
                code="media.inspect_failed",
                path=str(source_path),
            )

        project = self._build_project_from_media(
            source_path,
            media_info,
            project_name,
            project_id,
            asset_id,
            track_id,
            clip_id,
        )
        if project_path:
            target_path = Path(project_path).resolve()
        else:
            target_path, _ = self.store.find_or_create_project_for_media(
                source_path, project_name=project_name or source_path.stem
            )

        with self.store.project_lock(target_path):
            try:
                imported_media_path = self.store.import_asset_to_project(
                    source_path,
                    target_path,
                    preferred_name=source_path.name,
                )
            except Exception as exc:
                return self._failure(
                    "create_project_from_media",
                    f"Failed to import media into project workspace: {exc}",
                    code="media.import_failed",
                    path=str(target_path.parent / "media"),
                )
            if project.assets:
                project.assets[0].path = imported_media_path
                project.assets[0].metadata["workspace_media_path"] = imported_media_path
            project.metadata["project_path"] = str(target_path)
            project.metadata["workspace_media_path"] = imported_media_path
            report = self.store.validate(project)
            try:
                saved_path = self.store.save(project, target_path)
                self.store.register_media_project(source_path, saved_path)
            except Exception as exc:
                return self._failure(
                    "create_project_from_media",
                    f"Failed to save project: {exc}",
                    code="project.save_failed",
                    path=str(target_path),
                )

            return self._created_project_response(project, report, saved_path, source_path, media_info)
