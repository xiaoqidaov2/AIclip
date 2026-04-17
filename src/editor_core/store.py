from __future__ import annotations

import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Literal, Optional, Tuple, TypeVar

from .codec import project_from_json, project_from_xml, project_to_json, project_to_xml
from .project import Project
from .validation import ValidationReport, validate_project
from .workspace import ProjectWorkspace, WorkspaceRegistry


ProjectFormat = Literal["json", "xml"]
MutationResult = TypeVar("MutationResult")


class ProjectStore:
    """Load and save project files through the shared editor core model."""

    _path_locks_guard = threading.Lock()
    _path_locks: dict[Path, threading.RLock] = {}

    def __init__(self, registry: Optional[WorkspaceRegistry] = None) -> None:
        self.registry = registry or WorkspaceRegistry()

    @classmethod
    def _normalized_path(cls, path: str | Path) -> Path:
        return Path(path).resolve()

    @classmethod
    def _lock_for_path(cls, path: str | Path) -> threading.RLock:
        normalized = cls._normalized_path(path)
        with cls._path_locks_guard:
            lock = cls._path_locks.get(normalized)
            if lock is None:
                lock = threading.RLock()
                cls._path_locks[normalized] = lock
            return lock

    @contextmanager
    def project_lock(self, path: str | Path) -> Iterator[None]:
        lock = self._lock_for_path(path)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def load(self, path: str | Path, *, _already_locked: bool = False) -> Project:
        file_path = self._normalized_path(path)
        if not _already_locked:
            with self.project_lock(file_path):
                return self.load(file_path, _already_locked=True)

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
        _already_locked: bool = False,
    ) -> Path:
        file_path = self._normalized_path(path)
        if not _already_locked:
            with self.project_lock(file_path):
                return self.save(project, file_path, format=format, indent=indent, _already_locked=True)

        file_path.parent.mkdir(parents=True, exist_ok=True)

        target_format = format or ("xml" if file_path.suffix.lower() == ".xml" else "json")
        if target_format == "xml":
            content = project_to_xml(project)
        else:
            content = project_to_json(project, indent=indent)

        fd, temp_path_str = tempfile.mkstemp(
            dir=str(file_path.parent),
            prefix=f".{file_path.stem}.",
            suffix=f"{file_path.suffix}.tmp",
            text=True,
        )
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, file_path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
        return file_path

    def mutate(
        self,
        path: str | Path,
        mutator: Callable[[Project], MutationResult],
        *,
        output_path: Optional[str | Path] = None,
        format: Optional[ProjectFormat] = None,
        indent: int = 2,
    ) -> Tuple[Project, MutationResult, Path]:
        source_path = self._normalized_path(path)
        target_path = self._normalized_path(output_path or path)
        lock_path = source_path if source_path == target_path else target_path

        with self.project_lock(lock_path):
            project = self.load(source_path, _already_locked=True)
            result = mutator(project)
            saved_path = self.save(project, target_path, format=format, indent=indent, _already_locked=True)
        return project, result, saved_path

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
