import json
from typing import Any, Dict, Optional


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
        self.stage_contexts: list[Dict[str, Any]] = []
        self.stage_audit: list[Dict[str, Any]] = []

    @property
    def has_context(self) -> bool:
        return (
            self.last_tool_result is not None
            or self.last_validation is not None
            or self.last_render_state is not None
        )

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
        self.stage_contexts = []
        self.stage_audit = []

    def update_from_tool(self, tool_name: str, result: Any, tool_args: Optional[Dict[str, Any]] = None) -> None:
        normalized_result = result if isinstance(result, dict) else {"content": result}

        self.last_tool_name = tool_name
        self.last_tool_result = normalized_result
        self.last_tool_content = normalized_result.get("content")
        self.last_operation = normalized_result.get("operation") or tool_name
        self.last_project_version = normalized_result.get("project_version")

        decision = normalized_result.get("decision")
        if isinstance(decision, dict):
            self.last_decision = decision
        elif isinstance(normalized_result.get("state"), dict):
            self.last_decision = {
                "operation": self.last_operation,
                "code": normalized_result.get("code"),
                "status": normalized_result.get("status"),
                "state": normalized_result.get("state"),
                "next_actions": normalized_result.get("next_actions", []),
            }

        if isinstance(normalized_result.get("validation"), dict):
            self.last_validation = normalized_result["validation"]
        if isinstance(normalized_result.get("render_state"), dict):
            self.last_render_state = normalized_result["render_state"]

        state = normalized_result.get("state")
        if isinstance(state, dict):
            for key in ("project_path", "output_path", "media_path", "preview_path", "final_path", "subtitle_path"):
                value = state.get(key)
                if isinstance(value, str):
                    self.last_file_path = value
                    break

        if self.last_file_path is None and tool_args:
            for key in ("audio_path", "file_path", "video_path", "subtitle_path", "project_path", "output_path"):
                value = tool_args.get(key)
                if isinstance(value, str):
                    self.last_file_path = value
                    break

    def _compact_value(self, value: Any, max_length: int = 280) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, dict):
            try:
                text = json.dumps(value, ensure_ascii=False, default=str)
            except TypeError:
                text = str(value)
        else:
            text = str(value)

        text = text.strip()
        if len(text) > max_length:
            return text[: max_length - 3] + "..."
        return text

    def update_route_decision(self, decision: Dict[str, Any]) -> None:
        self.last_route_decision = decision

    def add_stage_context(self, context: Dict[str, Any]) -> None:
        self.stage_contexts.append(context)
        self.stage_contexts = self.stage_contexts[-5:]

    def add_stage_audit(self, audit: Dict[str, Any]) -> None:
        self.stage_audit.append(audit)
        self.stage_audit = self.stage_audit[-20:]

    def to_context_prompt(self) -> str:
        lines = ["Current session state:"]

        if self.active_skill:
            lines.append(f"- active_skill: {self.active_skill}")
        if self.last_route_decision:
            skill_name = self.last_route_decision.get("skill_name")
            reason = self.last_route_decision.get("reason")
            confidence = self.last_route_decision.get("confidence")
            locked = self.last_route_decision.get("locked")
            matched_terms = self.last_route_decision.get("matched_terms") or []
            if skill_name:
                lines.append(f"- route_skill: {skill_name}")
            if reason:
                lines.append(f"- route_reason: {reason}")
            if confidence is not None:
                lines.append(f"- route_confidence: {confidence}")
            lines.append(f"- route_locked: {locked}")
            if matched_terms:
                lines.append(f"- route_matches: {', '.join(map(str, matched_terms[:4]))}")

        if self.last_operation:
            lines.append(f"- operation: {self.last_operation}")
        if self.last_project_version is not None:
            lines.append(f"- project_version: {self.last_project_version}")
        if self.last_decision:
            code = self.last_decision.get("code")
            status = self.last_decision.get("status")
            if code or status:
                lines.append(f"- decision: code={code} status={status}")
            next_actions = self.last_decision.get("next_actions") or []
            if next_actions:
                lines.append(f"- next_actions: {', '.join(map(str, next_actions[:4]))}")
            state = self.last_decision.get("state")
            if isinstance(state, dict):
                compact = []
                for key in (
                    "project_path",
                    "output_path",
                    "media_path",
                    "subtitle_source_present",
                    "asset_count",
                    "track_count",
                    "subtitle_count",
                    "audio_stem_count",
                    "effect_count",
                ):
                    value = state.get(key)
                    if value not in (None, ""):
                        compact.append(f"{key}={value}")
                if compact:
                    lines.append(f"- state: {', '.join(compact)}")

        if self.last_validation:
            passed = self.last_validation.get("passed", True)
            lines.append(f"- validation: {'passed' if passed else 'failed'}")
            errors = self.last_validation.get("errors") or []
            if errors:
                lines.append(f"- validation_errors: {', '.join(map(str, errors[:3]))}")

        if self.last_render_state:
            ready = self.last_render_state.get("ready", False)
            lines.append(f"- render_ready: {ready}")
            blockers = self.last_render_state.get("blockers") or []
            if blockers:
                lines.append(f"- render_blockers: {', '.join(map(str, blockers[:3]))}")

        if self.last_file_path:
            lines.append(f"- file_path: {self.last_file_path}")

        if self.last_tool_content not in (None, ""):
            content_text = self._compact_value(self.last_tool_content)
            if content_text:
                lines.append(f"- tool_content: {content_text}")

        if self.stage_contexts:
            lines.append("- stage_contexts:")
            for item in self.stage_contexts[-3:]:
                phase = item.get("phase")
                summary = item.get("summary")
                if phase and summary:
                    lines.append(f"  - {phase}: {summary}")

        if self.stage_audit:
            lines.append("- stage_audit:")
            for item in self.stage_audit[-3:]:
                skill = item.get("skill")
                tool = item.get("tool")
                allowed = item.get("allowed_tools") or []
                if skill and tool:
                    lines.append(f"  - {skill}: {tool} allowed={', '.join(map(str, allowed[:4]))}")

        if not self.has_context:
            lines.append("- no reusable tool output yet")

        return "\n".join(lines)
