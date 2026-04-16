from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolChange:
    type: str
    id: str
    field: str
    before: Any = None
    after: Any = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationSnapshot:
    passed: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class RenderState:
    ready: bool = False
    blockers: List[str] = field(default_factory=list)
    preview_path: Optional[str] = None
    final_path: Optional[str] = None


@dataclass
class ArtifactRef:
    type: str
    path: str
    label: Optional[str] = None
    checksum: Optional[str] = None


@dataclass
class ToolResult:
    ok: bool
    status: str
    code: str
    message: str
    operation: str
    entity: Optional[str] = None
    project_id: Optional[str] = None
    project_version: Optional[int] = None
    changes: List[ToolChange] = field(default_factory=list)
    validation: ValidationSnapshot = field(default_factory=ValidationSnapshot)
    render_state: RenderState = field(default_factory=RenderState)
    artifacts: List[ArtifactRef] = field(default_factory=list)
    next_actions: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    decision: Dict[str, Any] = field(default_factory=dict)
    payload: Any = None
    content: Any = None
    summary: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=_utc_now)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["summary"] = self.summary or self.message
        data["content"] = self.content
        if not data.get("decision"):
            data["decision"] = {
                "operation": self.operation,
                "code": self.code,
                "status": self.status,
                "ok": self.ok,
                "project_id": self.project_id,
                "project_version": self.project_version,
                "validation": asdict(self.validation),
                "render_state": asdict(self.render_state),
                "state": dict(self.state),
                "next_actions": list(self.next_actions),
            }

        if isinstance(self.payload, dict):
            for key, value in self.payload.items():
                data.setdefault(key, value)
        elif self.payload is not None and "content" not in data:
            data["content"] = self.payload

        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_validation(raw: Any) -> ValidationSnapshot:
    if isinstance(raw, ValidationSnapshot):
        return raw
    if isinstance(raw, dict):
        return ValidationSnapshot(
            passed=bool(raw.get("passed", True)),
            warnings=[str(item) for item in _ensure_list(raw.get("warnings"))],
            errors=[str(item) for item in _ensure_list(raw.get("errors"))],
        )
    return ValidationSnapshot()


def _normalize_render_state(raw: Any) -> RenderState:
    if isinstance(raw, RenderState):
        return raw
    if isinstance(raw, dict):
        return RenderState(
            ready=bool(raw.get("ready", False)),
            blockers=[str(item) for item in _ensure_list(raw.get("blockers"))],
            preview_path=raw.get("preview_path"),
            final_path=raw.get("final_path"),
        )
    return RenderState()


def _normalize_changes(raw: Any) -> List[ToolChange]:
    if not raw:
        return []
    changes: List[ToolChange] = []
    for item in _ensure_list(raw):
        if isinstance(item, ToolChange):
            changes.append(item)
        elif isinstance(item, dict):
            changes.append(
                ToolChange(
                    type=str(item.get("type", "unknown")),
                    id=str(item.get("id", "")),
                    field=str(item.get("field", "")),
                    before=item.get("before"),
                    after=item.get("after"),
                    details=dict(item.get("details", {})),
                )
            )
    return changes


def _normalize_artifacts(raw: Any) -> List[ArtifactRef]:
    if not raw:
        return []
    artifacts: List[ArtifactRef] = []
    for item in _ensure_list(raw):
        if isinstance(item, ArtifactRef):
            artifacts.append(item)
        elif isinstance(item, dict):
            artifacts.append(
                ArtifactRef(
                    type=str(item.get("type", "file")),
                    path=str(item.get("path", "")),
                    label=item.get("label"),
                    checksum=item.get("checksum"),
                )
            )
    return artifacts


def normalize_tool_result(
    operation: str,
    raw: Any,
    *,
    entity: Optional[str] = None,
    project_id: Optional[str] = None,
    project_version: Optional[int] = None,
) -> Dict[str, Any]:
    if hasattr(raw, "to_dict") and callable(getattr(raw, "to_dict")):
        raw = raw.to_dict()
    elif is_dataclass(raw):
        raw = asdict(raw)

    if isinstance(raw, dict) and {"status", "code", "message"}.issubset(raw.keys()):
        result = dict(raw)
        result.setdefault("operation", operation)
        result.setdefault("summary", result["message"])
        result.setdefault(
            "decision",
            {
                "operation": result["operation"],
                "code": result.get("code"),
                "status": result.get("status"),
                "ok": result.get("ok", str(result.get("status", "")).lower() not in {"error", "failed", "fail"}),
                "project_id": result.get("project_id"),
                "project_version": result.get("project_version"),
                "validation": result.get("validation"),
                "render_state": result.get("render_state"),
                "state": result.get("state", {}),
                "next_actions": _ensure_list(result.get("next_actions")),
            },
        )
        if "ok" not in result:
            result["ok"] = str(result.get("status", "")).lower() not in {"error", "failed", "fail"}
        return result

    if isinstance(raw, dict):
        ok = bool(raw.get("ok", True))
        status = str(raw.get("status") or ("ok" if ok else "error"))
        message = str(raw.get("message") or raw.get("summary") or operation.replace("_", " "))
        result = ToolResult(
            ok=ok,
            status=status,
            code=str(raw.get("code") or f"{operation}.{status}"),
            message=message,
            operation=operation,
            entity=entity,
            project_id=project_id or raw.get("project_id"),
            project_version=project_version if project_version is not None else raw.get("project_version"),
            changes=_normalize_changes(raw.get("changes")),
            validation=_normalize_validation(raw.get("validation")),
            render_state=_normalize_render_state(raw.get("render_state")),
            artifacts=_normalize_artifacts(raw.get("artifacts")),
            next_actions=[str(item) for item in _ensure_list(raw.get("next_actions"))],
            state=dict(raw.get("state", {})) if isinstance(raw.get("state"), dict) else {},
            payload=raw,
            content=raw.get("content", raw),
            summary=str(raw.get("summary") or message),
            error=raw.get("error"),
        )
        result.decision = {
            "operation": operation,
            "code": result.code,
            "status": result.status,
            "ok": result.ok,
            "project_id": result.project_id,
            "project_version": result.project_version,
            "validation": asdict(result.validation),
            "render_state": asdict(result.render_state),
            "state": result.state,
            "next_actions": list(result.next_actions),
        }

        for key in (
            "output_path",
            "source_path",
            "segment_count",
            "format",
            "language",
            "duration",
            "size",
            "entries",
            "directory_path",
            "include_hidden",
        ):
            if key in raw and key not in result.state:
                result.state[key] = raw[key]

        return result.to_dict()

    message = str(raw).strip()
    result = ToolResult(
        ok=True,
        status="ok",
        code=f"{operation}.ok",
        message=message or operation.replace("_", " "),
        operation=operation,
        entity=entity,
        project_id=project_id,
        project_version=project_version,
        payload=raw,
        content=raw,
        summary=message or operation.replace("_", " "),
    )
    result.decision = {
        "operation": operation,
        "code": result.code,
        "status": result.status,
        "ok": result.ok,
        "project_id": result.project_id,
        "project_version": result.project_version,
        "validation": asdict(result.validation),
        "render_state": asdict(result.render_state),
        "state": result.state,
        "next_actions": [],
    }
    return result.to_dict()


def serialize_tool_result(operation: str, raw: Any, **kwargs: Any) -> str:
    return json.dumps(normalize_tool_result(operation, raw, **kwargs), ensure_ascii=False, default=str)
