from __future__ import annotations

from typing import Optional

from .commands_base import Command, CommandResult
from ..contracts import ToolChange, ValidationSnapshot
from ..project import Comment, Project


class AddCommentCommand(Command):
    name = "add_comment"

    def __init__(self, comment: Comment):
        self.comment = comment

    def execute(self, project: Project) -> CommandResult:
        if any(item.id == self.comment.id for item in project.comments):
            return CommandResult(ok=False, code="comment.duplicate", message=f"Comment already exists: {self.comment.id}", validation=ValidationSnapshot(passed=False, errors=[f"Duplicate comment id: {self.comment.id}"]))
        project.comments.append(self.comment)
        project.bump_version()
        return CommandResult(ok=True, code="comment.added", message="Comment added", changes=[ToolChange(type="comment", id=self.comment.id, field="comments", after=self.comment)], state={"project_version": project.version})


class UpdateCommentCommand(Command):
    name = "update_comment"

    def __init__(self, comment_id: str, text: Optional[str] = None, anchor: Optional[str] = None, timecode: Optional[float] = None, locked: Optional[bool] = None):
        self.comment_id = comment_id
        self.text = text
        self.anchor = anchor
        self.timecode = timecode
        self.locked = locked

    def execute(self, project: Project) -> CommandResult:
        comment = next((item for item in project.comments if item.id == self.comment_id), None)
        if comment is None:
            return CommandResult(ok=False, code="comment.not_found", message=f"Comment not found: {self.comment_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]))
        before = comment.__dict__.copy()
        for attr in ("text", "anchor", "timecode", "locked"):
            value = getattr(self, attr)
            if value is not None:
                setattr(comment, attr, value)
        project.bump_version()
        return CommandResult(ok=True, code="comment.updated", message="Comment updated", changes=[ToolChange(type="comment", id=self.comment_id, field="comment", before=before, after=comment)], state={"project_version": project.version})


class RemoveCommentCommand(Command):
    name = "remove_comment"

    def __init__(self, comment_id: str):
        self.comment_id = comment_id

    def execute(self, project: Project) -> CommandResult:
        index = next((i for i, item in enumerate(project.comments) if item.id == self.comment_id), None)
        if index is None:
            return CommandResult(ok=False, code="comment.not_found", message=f"Comment not found: {self.comment_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]))
        removed = project.comments.pop(index)
        project.bump_version()
        return CommandResult(ok=True, code="comment.removed", message="Comment removed", changes=[ToolChange(type="comment", id=self.comment_id, field="comments", before=removed)], state={"project_version": project.version})


class LockCommentCommand(Command):
    name = "lock_comment"

    def __init__(self, comment_id: str, locked: bool = True):
        self.comment_id = comment_id
        self.locked = locked

    def execute(self, project: Project) -> CommandResult:
        comment = next((item for item in project.comments if item.id == self.comment_id), None)
        if comment is None:
            return CommandResult(ok=False, code="comment.not_found", message=f"Comment not found: {self.comment_id}", validation=ValidationSnapshot(passed=False, errors=[f"Missing comment: {self.comment_id}"]))
        before = comment.locked
        comment.locked = self.locked
        project.bump_version()
        return CommandResult(ok=True, code="comment.locked" if self.locked else "comment.unlocked", message="Comment lock updated", changes=[ToolChange(type="comment", id=self.comment_id, field="locked", before=before, after=comment.locked)], state={"project_version": project.version})
