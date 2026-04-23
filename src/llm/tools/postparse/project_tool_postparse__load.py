from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseLoadMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _load(self, project_path: str):

        path = Path(project_path)

        if not path.exists():

            return None, self._failure(
                "load_project",
                f"Project file not found: {project_path}",
                code="project.not_found",
                path=str(path),
            )

        try:

            return self.store.load(path), None

        except Exception as exc:

            return None, self._failure(
                "load_project",
                f"Failed to load project: {exc}",
                code="project.load_failed",
                path=str(path),
            )
