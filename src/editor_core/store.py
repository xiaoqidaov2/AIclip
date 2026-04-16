from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Tuple

from .codec import project_from_json, project_from_xml, project_to_json, project_to_xml
from .project import Project
from .validation import ValidationReport, validate_project
from .workspace import ProjectWorkspace, WorkspaceRegistry


ProjectFormat = Literal["json", "xml"]


class ProjectStore:
    """Load and save project files through the shared editor core model."""

    def __init__(self, registry: Optional[WorkspaceRegistry] = None) -> None:
        self.registry = registry or WorkspaceRegistry()

    def load(self, path: str | Path) -> Project:
        file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        suffix = file_path.suffix.lower()
        if suffix == ".xml":
            return project_from_xml(text)
        return project_from_json(text)

    def save(
        self,
        project: Project,
        path: str | Path,
        *,
        format: Optional[ProjectFormat] = None,
        indent: int = 2,
    ) -> Path:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        target_format = format or ("xml" if file_path.suffix.lower() == ".xml" else "json")
        if target_format == "xml":
            content = project_to_xml(project)
        else:
            content = project_to_json(project, indent=indent)

        file_path.write_text(content, encoding="utf-8")
        return file_path

    def validate(self, project: Project) -> ValidationReport:
        return validate_project(project)

    def workspace_for_project(self, project_path: str | Path) -> ProjectWorkspace:
        return ProjectWorkspace(Path(project_path).resolve().parent)

    def resolve_asset_path(self, asset_path: str | Path, project_path: str | Path) -> Path:
        workspace = self.workspace_for_project(project_path)
        return workspace.resolve_path(asset_path)

    def find_project_for_media(self, media_path: str | Path) -> Optional[Path]:
        workspace = self.registry.find(media_path)
        if workspace is None:
            return None
        if workspace.project_file.exists():
            return workspace.project_file
        return None

    def find_or_create_project_for_media(
        self,
        media_path: str | Path,
        project_name: Optional[str] = None,
    ) -> Tuple[Path, bool]:
        workspace, created = self.registry.find_or_create(media_path, project_name=project_name)
        return workspace.project_file, created

    def register_media_project(self, media_path: str | Path, project_path: str | Path) -> None:
        workspace = self.workspace_for_project(project_path)
        workspace.ensure()
        self.registry.register(media_path, workspace)
