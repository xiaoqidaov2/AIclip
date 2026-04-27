import json
from typing import Any, Dict, Optional

from .state_impl import build_context_prompt, compact_value, update_from_tool_state


class SessionState:
    """Structured results from the most recent tool calls."""

    def __init__(self) -> None:
        self.active_skill: Optional[str] = None
        self.last_route_decision: Optional[Dict[str, Any]] = None
        self.last_tool_name: Optional[str] = None
        self.last_operation: Optional[str] = None
        self.last_project_version: Optional[int] = None
        self.last_tool_result: Optional[Dict[str, Any]] = None
        self.last_tool_content: Optional[Any] = None
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_validation: Optional[Dict[str, Any]] = None
        self.last_render_state: Optional[Dict[str, Any]] = None
        self.last_file_path: Optional[str] = None
        self.last_short_video_score: Optional[float] = None
        self.last_short_video_diagnosis: list[str] = []
        self.stage_contexts: list[Dict[str, Any]] = []
        self.stage_audit: list[Dict[str, Any]] = []

    @property
    def has_context(self) -> bool:
        return self.last_tool_result is not None or self.last_validation is not None or self.last_render_state is not None

    def clear(self) -> None:
        self.active_skill = None
        self.last_route_decision = None
        self.last_tool_name = None
        self.last_operation = None
        self.last_project_version = None
        self.last_tool_result = None
        self.last_tool_content = None
        self.last_decision = None
        self.last_validation = None
        self.last_render_state = None
        self.last_file_path = None
        self.last_short_video_score = None
        self.last_short_video_diagnosis = []
        self.stage_contexts = []
        self.stage_audit = []

    def update_from_tool(self, tool_name: str, result: Any, tool_args: Optional[Dict[str, Any]] = None) -> None:
        update_from_tool_state(self, tool_name, result, tool_args)

    def _compact_value(self, value: Any, max_length: int = 280) -> str:
        return compact_value(value, max_length)

    def update_route_decision(self, decision: Dict[str, Any]) -> None:
        self.last_route_decision = decision

    def add_stage_context(self, context: Dict[str, Any]) -> None:
        self.stage_contexts.append(context)
        self.stage_contexts = self.stage_contexts[-5:]

    def add_stage_audit(self, audit: Dict[str, Any]) -> None:
        self.stage_audit.append(audit)
        self.stage_audit = self.stage_audit[-20:]

    def to_context_prompt(self) -> str:
        return build_context_prompt(self)
