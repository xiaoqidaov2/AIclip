import json
from typing import Any, Dict, Optional


def update_from_tool_state(state: Any, tool_name: str, result: Any, tool_args: Optional[Dict[str, Any]] = None) -> None:
    normalized_result = result if isinstance(result, dict) else {"content": result}
    state.last_tool_name = tool_name
    state.last_tool_result = normalized_result
    state.last_tool_content = normalized_result.get("content")
    state.last_operation = normalized_result.get("operation") or tool_name
    state.last_project_version = normalized_result.get("project_version")
    decision = normalized_result.get("decision")
    if isinstance(decision, dict):
        state.last_decision = decision
    elif isinstance(normalized_result.get("state"), dict):
        state.last_decision = {"operation": state.last_operation, "code": normalized_result.get("code"), "status": normalized_result.get("status"), "state": normalized_result.get("state"), "next_actions": normalized_result.get("next_actions", [])}
    if isinstance(normalized_result.get("validation"), dict):
        state.last_validation = normalized_result["validation"]
    if isinstance(normalized_result.get("render_state"), dict):
        state.last_render_state = normalized_result["render_state"]
    local_state = normalized_result.get("state")
    if isinstance(local_state, dict):
        score = local_state.get("short_video_score")
        if score not in (None, ""):
            try:
                state.last_short_video_score = float(score)
            except (TypeError, ValueError):
                pass
        diagnosis = local_state.get("short_video_diagnosis")
        if isinstance(diagnosis, list):
            state.last_short_video_diagnosis = [str(item) for item in diagnosis if str(item).strip()]
    payload = normalized_result.get("payload")
    if isinstance(payload, dict):
        short_video = payload.get("short_video")
        if isinstance(short_video, dict):
            score = short_video.get("score")
            if score not in (None, ""):
                try:
                    state.last_short_video_score = float(score)
                except (TypeError, ValueError):
                    pass
            diagnosis = short_video.get("diagnosis")
            if isinstance(diagnosis, list):
                state.last_short_video_diagnosis = [str(item) for item in diagnosis if str(item).strip()]
    if isinstance(local_state, dict):
        for key in ("project_path", "output_path", "media_path", "preview_path", "final_path", "subtitle_path"):
            value = local_state.get(key)
            if isinstance(value, str):
                state.last_file_path = value
                break
    if state.last_file_path is None and tool_args:
        for key in ("audio_path", "file_path", "video_path", "subtitle_path", "project_path", "output_path"):
            value = tool_args.get(key)
            if isinstance(value, str):
                state.last_file_path = value
                break


def compact_value(value: Any, max_length: int = 280) -> str:
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
    return text[: max_length - 3] + "..." if len(text) > max_length else text


def build_context_prompt(state: Any) -> str:
    lines = ["Current session state:"]
    if state.active_skill:
        lines.append(f"- active_skill: {state.active_skill}")
    if state.last_route_decision:
        skill_name = state.last_route_decision.get("skill_name")
        reason = state.last_route_decision.get("reason")
        confidence = state.last_route_decision.get("confidence")
        locked = state.last_route_decision.get("locked")
        matched_terms = state.last_route_decision.get("matched_terms") or []
        if skill_name:
            lines.append(f"- route_skill: {skill_name}")
        if reason:
            lines.append(f"- route_reason: {reason}")
        if confidence is not None:
            lines.append(f"- route_confidence: {confidence}")
        lines.append(f"- route_locked: {locked}")
        if matched_terms:
            lines.append(f"- route_matches: {', '.join(map(str, matched_terms[:4]))}")
    if state.last_operation:
        lines.append(f"- operation: {state.last_operation}")
    if state.last_project_version is not None:
        lines.append(f"- project_version: {state.last_project_version}")
    if state.last_decision:
        code = state.last_decision.get("code")
        status = state.last_decision.get("status")
        if code or status:
            lines.append(f"- decision: code={code} status={status}")
    if state.last_validation:
        warnings = state.last_validation.get("warnings") or []
        errors = state.last_validation.get("errors") or []
        if warnings:
            lines.append(f"- validation_warnings: {compact_value(warnings)}")
        if errors:
            lines.append(f"- validation_errors: {compact_value(errors)}")
    if state.last_render_state:
        ready = state.last_render_state.get("ready")
        blockers = state.last_render_state.get("blockers") or []
        lines.append(f"- render_ready: {ready}")
        if blockers:
            lines.append(f"- render_blockers: {compact_value(blockers)}")
    if state.last_short_video_score is not None:
        lines.append(f"- short_video_score: {state.last_short_video_score:.1f}")
    if state.last_short_video_diagnosis:
        lines.append(f"- short_video_diagnosis: {compact_value(state.last_short_video_diagnosis)}")
    if state.last_file_path:
        lines.append(f"- current_file: {state.last_file_path}")
    if state.stage_contexts:
        lines.append(f"- recent_stages: {compact_value(state.stage_contexts[-3:])}")
    if state.stage_audit:
        lines.append(f"- recent_audit: {compact_value(state.stage_audit[-5:])}")
    return "\n".join(lines)
