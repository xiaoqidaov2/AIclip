from __future__ import annotations

from typing import Any, Dict

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Asset, Project


class SetProjectMetadataCommand(Command):
    name = "set_project_metadata"

    def __init__(self, metadata: Dict[str, Any]):
        self.metadata = dict(metadata)

    def execute(self, project: Project) -> CommandResult:
        before = dict(project.metadata)
        project.metadata.update(self.metadata)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="project.metadata.updated",
            message="Project metadata updated",
            changes=[ToolChange(type="project", id=project.id, field="metadata", before=before, after=dict(project.metadata))],
            state={"project_version": project.version},
        )


class AddAssetCommand(Command):
    name = "add_asset"

    def __init__(self, asset: Asset):
        self.asset = asset

    def execute(self, project: Project) -> CommandResult:
        if project.find_asset(self.asset.id):
            return CommandResult(
                ok=False,
                code="asset.duplicate",
                message=f"Asset already exists: {self.asset.id}",
                validation=ValidationSnapshot(passed=False, errors=[f"Duplicate asset id: {self.asset.id}"]),
            )
        project.assets.append(self.asset)
        project.bump_version()
        return CommandResult(
            ok=True,
            code="asset.added",
            message="Asset added",
            changes=[ToolChange(type="asset", id=self.asset.id, field="assets", after=self.asset)],
            state={"project_version": project.version},
        )
