from __future__ import annotations


from dataclasses import dataclass


from datetime import datetime, timezone


import json


import os


from pathlib import Path


import re


from typing import Any, Dict, Optional, Tuple


def _source_key(source_path: str | Path) -> str:

    resolved = str(Path(source_path).resolve())

    # Windows is case-insensitive, so normalize key casing.

    if os.name == "nt":

        return os.path.normcase(resolved)

    return resolved


def _slugify(value: str) -> str:

    text = re.sub(r"\s+", "_", value.strip())

    text = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]", "", text)

    return text or "project"


@dataclass(frozen=True)
class ProjectWorkspace:

    root: Path

    @property
    def project_file(self) -> Path:

        return self.root / "project.json"

    @property
    def media_dir(self) -> Path:

        return self.root / "media"

    @property
    def exports_dir(self) -> Path:

        return self.root / "exports"

    @property
    def cache_dir(self) -> Path:

        return self.root / "cache"

    def ensure(self) -> None:

        self.root.mkdir(parents=True, exist_ok=True)

        self.media_dir.mkdir(parents=True, exist_ok=True)

        self.exports_dir.mkdir(parents=True, exist_ok=True)

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, raw_path: str | Path) -> Path:

        path = Path(raw_path)

        workspace_root = self.root.resolve()

        if path.is_absolute():

            resolved = path.resolve()

        else:

            resolved = (workspace_root / path).resolve()

        # Guard against path traversal: resolved path must stay within workspace root.

        try:

            resolved.relative_to(workspace_root)

        except ValueError:

            raise ValueError(

                f"Asset path escapes workspace boundary: {raw_path!r} resolved to {resolved}"

            )

        return resolved

    def to_storage_path(self, path: str | Path) -> str:

        candidate = Path(path).resolve()

        try:

            return candidate.relative_to(self.root.resolve()).as_posix()

        except ValueError:

            return str(candidate)

    def default_export_path(self, stem_hint: str = "final") -> Path:

        safe_stem = _slugify(stem_hint)

        return self.exports_dir / f"{safe_stem}.mp4"


class WorkspaceRegistry:

    def __init__(self, base_dir: Optional[str | Path] = None) -> None:

        configured = base_dir or os.getenv("AICLIP_WORKSPACE", "")

        if configured:

            root = Path(configured).expanduser()

        else:

            root = Path.home() / ".aiclip"

        self.root = root.resolve()

        self.projects_dir = self.root / "projects"

        self.registry_path = self.root / "registry.json"

    def _empty(self) -> Dict[str, Any]:

        return {"version": 1, "entries": {}}

    def _load_data(self) -> Dict[str, Any]:

        if not self.registry_path.exists():

            return self._empty()

        try:

            data = json.loads(self.registry_path.read_text(encoding="utf-8"))

        except Exception:

            return self._empty()

        if not isinstance(data, dict):

            return self._empty()

        data.setdefault("version", 1)

        entries = data.get("entries")

        if not isinstance(entries, dict):

            data["entries"] = {}

        return data

    def _save_data(self, data: Dict[str, Any]) -> None:

        self.root.mkdir(parents=True, exist_ok=True)

        self.projects_dir.mkdir(parents=True, exist_ok=True)

        content = json.dumps(data, ensure_ascii=False, indent=2)

        import tempfile

        fd, tmp_path_str = tempfile.mkstemp(

            dir=str(self.root),

            prefix=".registry.",

            suffix=".tmp",

            text=True,

        )

        try:

            with os.fdopen(fd, "w", encoding="utf-8") as f:

                f.write(content)

                f.flush()

                os.fsync(f.fileno())

            os.replace(tmp_path_str, str(self.registry_path))

        finally:

            tmp = Path(tmp_path_str)

            if tmp.exists():

                tmp.unlink(missing_ok=True)

    def find(self, source_path: str | Path) -> Optional[ProjectWorkspace]:

        key = _source_key(source_path)

        data = self._load_data()

        entries = data.get("entries", {})

        record = entries.get(key)

        if not isinstance(record, dict):

            return None

        workspace_raw = record.get("workspace")

        if not workspace_raw:

            return None

        workspace = ProjectWorkspace(Path(workspace_raw))

        if workspace.project_file.exists():

            return workspace

        return None

    def register(self, source_path: str | Path, workspace: ProjectWorkspace) -> None:

        key = _source_key(source_path)

        data = self._load_data()

        entries = data.setdefault("entries", {})

        entries[key] = {
            "workspace": str(workspace.root.resolve()),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        self._save_data(data)

    def _new_workspace(
        self, source_path: str | Path, project_name: Optional[str] = None
    ) -> ProjectWorkspace:

        source = Path(source_path)

        base = _slugify(project_name or source.stem)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        candidate = self.projects_dir / f"{base}_{stamp}"

        suffix = 1

        while candidate.exists():

            candidate = self.projects_dir / f"{base}_{stamp}_{suffix:02d}"

            suffix += 1

        workspace = ProjectWorkspace(candidate)

        workspace.ensure()

        return workspace

    def find_or_create(
        self, source_path: str | Path, project_name: Optional[str] = None
    ) -> Tuple[ProjectWorkspace, bool]:

        existing = self.find(source_path)

        if existing is not None:

            existing.ensure()

            return existing, False

        workspace = self._new_workspace(source_path, project_name)

        self.register(source_path, workspace)

        return workspace, True
