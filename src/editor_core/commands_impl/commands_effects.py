from __future__ import annotations

from typing import Any, Dict, Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Effect, Project


class AddEffectCommand(Command):
    name = "add_effect"

    def __init__(self, effect: Effect):
        self.effect = effect

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.effect.id for item in project.effects):
            return CommandResult(ok=False, code="effect.duplicate", message=f"Effect already exists: {self.effect.id}", validation=ValidationSnapshot(passed=False, errors=[f"Duplicate effect id: {self.effect.id}"]))
        project.effects.append(self.effect)
        project.bump_version()
        return CommandResult(ok=True, code="effect.added", message="Effect added", changes=[ToolChange(type="effect", id=self.effect.id, field="effects", after=self.effect)], state={"project_version": project.version})


class UpdateEffectCommand(Command):
    name = "update_effect"

    def __init__(self, effect_id: str, target_id: Optional[str] = None, kind: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None):
        self.effect_id = effect_id
        self.target_id = target_id
        self.kind = kind
        self.parameters = parameters or {}

    def execute(self, project: Project) -> CommandResult:
        effect = next((item for item in project.effects if item.id == self.effect_id), None)
        if effect is None:
            return CommandResult(ok=False, code="effect.not_found", message=f"Effect not found: {self.effect_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing effect: {self.effect_id}"]))
        before = effect.__dict__.copy()
        if self.target_id is not None:
            effect.target_id = self.target_id
        if self.kind is not None:
            effect.kind = self.kind
        if self.parameters:
            effect.parameters.update(self.parameters)
        project.bump_version()
        return CommandResult(ok=True, code="effect.updated", message="Effect updated", changes=[ToolChange(type="effect", id=self.effect_id, field="effect", before=before, after=effect)], state={"project_version": project.version})


class RemoveEffectCommand(Command):
    name = "remove_effect"

    def __init__(self, effect_id: str):
        self.effect_id = effect_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.effects) if item.id == self.effect_id), None)
        if index is None:
            return CommandResult(ok=False, code="effect.not_found", message=f"Effect not found: {self.effect_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing effect: {self.effect_id}"]))
        removed = project.effects.pop(index)
        project.bump_version()
        return CommandResult(ok=True, code="effect.removed", message="Effect removed", changes=[ToolChange(type="effect", id=self.effect_id, field="effects", before=removed)], state={"project_version": project.version})
