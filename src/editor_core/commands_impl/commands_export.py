from __future__ import annotations

from .commands_base import Command, CommandResult
from ..contracts import ToolChange
from ..project import ExportPreset, Project


class SetExportPresetCommand(Command):
    name = "set_export_preset"

    def __init__(self, preset: ExportPreset):
        self.preset = preset

    def execute(self, project: Project) -> CommandResult:
        existing = next((item for item in project.export_presets if item.id == self.preset.id), None)
        before = existing.__dict__.copy() if existing else None
        if existing is None:
            project.export_presets.append(self.preset)
        else:
            existing.name = self.preset.name
            existing.format = self.preset.format
            existing.settings.update(self.preset.settings)
            existing.metadata.update(self.preset.metadata)
        project.bump_version()
        return CommandResult(ok=True, code="export_preset.updated", message="Export preset updated", changes=[ToolChange(type="export_preset", id=self.preset.id, field="export_presets", before=before, after=self.preset)], state={"project_version": project.version})
