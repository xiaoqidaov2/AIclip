from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from .contracts_models import ArtifactRef, RenderState, ToolChange, ToolResult, ValidationSnapshot


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_validation(raw: Any) -> ValidationSnapshot:
    if isinstance(raw, ValidationSnapshot):
        return raw
    if isinstance(raw, dict):
        return ValidationSnapshot(passed=bool(raw.get("passed", True)), warnings=[str(item) for item in ensure_list(raw.get("warnings"))], errors=[str(item) for item in ensure_list(raw.get("errors"))])
    return ValidationSnapshot()


def normalize_render_state(raw: Any) -> RenderState:
    if isinstance(raw, RenderState):
        return raw
    if isinstance(raw, dict):
        return RenderState(ready=bool(raw.get("ready", False)), blockers=[str(item) for item in ensure_list(raw.get("blockers"))], preview_path=raw.get("preview_path"), final_path=raw.get("final_path"))
    return RenderState()


def normalize_changes(raw: Any) -> List[ToolChange]:
    if not raw:
        return []
    changes: List[ToolChange] = []
    for item in ensure_list(raw):
        if isinstance(item, ToolChange):
            changes.append(item)
        elif isinstance(item, dict):
            changes.append(ToolChange(type=str(item.get("type", "unknown")), id=str(item.get("id", "")), field=str(item.get("field", "")), before=item.get("before"), after=item.get("after"), details=dict(item.get("details", {}))))
    return changes


def normalize_artifacts(raw: Any) -> List[ArtifactRef]:
    if not raw:
        return []
    artifacts: List[ArtifactRef] = []
    for item in ensure_list(raw):
        if isinstance(item, ArtifactRef):
            artifacts.append(item)
        elif isinstance(item, dict):
            artifacts.append(ArtifactRef(type=str(item.get("type", "file")), path=str(item.get("path", "")), label=item.get("label"), checksum=item.get("checksum")))
    return artifacts


def normalize_tool_result(operation: str, raw: Any, *, entity: Optional[str] = None, project_id: Optional[str] = None, project_version: Optional[int] = None, compact: bool = True) -> Dict[str, Any]:
    if hasattr(raw, "to_dict") and callable(getattr(raw, "to_dict")):
        raw = raw.to_dict(compact=compact)
    elif is_dataclass(raw) and not isinstance(raw, type):
        raw = asdict(raw)
    if isinstance(raw, dict) and {"status", "code", "message"}.issubset(raw.keys()):
        result_dict = dict(raw)
        result_dict.setdefault("operation", operation)
        if not compact:
            result_dict.setdefault("summary", result_dict["message"])
            result_dict.setdefault("decision", {"ok": result_dict.get("ok", str(result_dict.get("status", "")).lower() not in {"error", "failed", "fail"}), "next_actions": ensure_list(result_dict.get("next_actions"))})
        if "ok" not in result_dict:
            result_dict["ok"] = str(result_dict.get("status", "")).lower() not in {"error", "failed", "fail"}
        return result_dict
    if isinstance(raw, dict):
        ok = bool(raw.get("ok", True))
        status = str(raw.get("status") or ("ok" if ok else "error"))
        message = str(raw.get("message") or raw.get("summary") or operation.replace("_", " "))
        tool_result = ToolResult(ok=ok, status=status, code=str(raw.get("code") or f"{operation}.{status}"), message=message, operation=operation, entity=entity, project_id=project_id or raw.get("project_id"), project_version=project_version if project_version is not None else raw.get("project_version"), changes=normalize_changes(raw.get("changes")), validation=normalize_validation(raw.get("validation")), render_state=normalize_render_state(raw.get("render_state")), artifacts=normalize_artifacts(raw.get("artifacts")), next_actions=[str(item) for item in ensure_list(raw.get("next_actions"))], state=dict(raw.get("state", {})) if isinstance(raw.get("state"), dict) else {}, payload=raw, content=raw.get("content", raw), summary=str(raw.get("summary") or message), error=raw.get("error"))
        tool_result.decision = {"ok": tool_result.ok, "next_actions": list(tool_result.next_actions)}
        for key in ("output_path", "source_path", "segment_count", "format", "language", "duration", "size", "entries", "directory_path", "include_hidden"):
            if key in raw and key not in tool_result.state:
                tool_result.state[key] = raw[key]
        return tool_result.to_dict(compact=compact)
    message = str(raw).strip()
    tool_result = ToolResult(ok=True, status="ok", code=f"{operation}.ok", message=message or operation.replace("_", " "), operation=operation, entity=entity, project_id=project_id, project_version=project_version, payload=raw, content=raw, summary=message or operation.replace("_", " "))
    tool_result.decision = {"ok": tool_result.ok, "next_actions": []}
    return tool_result.to_dict(compact=compact)


def serialize_tool_result(operation: str, raw: Any, **kwargs: Any) -> str:
    return json.dumps(normalize_tool_result(operation, raw, **kwargs), ensure_ascii=False, default=str)
