from typing import Any, Dict, Optional


class SessionState:
    """Structured results from the most recent tool calls."""

    def __init__(self) -> None:
        self.last_tool_name: Optional[str] = None
        self.last_operation: Optional[str] = None
        self.last_project_version: Optional[int] = None
        self.last_tool_result: Optional[Dict[str, Any]] = None
        self.last_decision: Optional[Dict[str, Any]] = None
        self.last_validation: Optional[Dict[str, Any]] = None
        self.last_render_state: Optional[Dict[str, Any]] = None
        self.last_file_path: Optional[str] = None

    @property
    def has_context(self) -> bool:
        return (
            self.last_tool_result is not None
            or self.last_validation is not None
            or self.last_render_state is not None
        )

    def clear(self) -> None:
        self.last_tool_name = None
        self.last_operation = None
        self.last_project_version = None
        self.last_tool_result = None
        self.last_decision = None
        self.last_validation = None
        self.last_render_state = None
        self.last_file_path = None

    def update_from_tool(self, tool_name: str, result: Any, tool_args: Optional[Dict[str, Any]] = None) -> None:
        normalized_result = result if isinstance(result, dict) else {"content": result}

        self.last_tool_name = tool_name
        self.last_tool_result = normalized_result
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

    def to_context_prompt(self) -> str:
        lines = ["Current session state:"]

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

        if not self.has_context:
            lines.append("- no reusable tool output yet")

        return "\n".join(lines)
