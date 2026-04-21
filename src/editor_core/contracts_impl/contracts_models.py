from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field as dataclass_field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolChange:
    type: str
    id: str
    field: str
    before: Any = None
    after: Any = None
    details: Dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class ValidationSnapshot:
    passed: bool = True
    warnings: List[str] = dataclass_field(default_factory=list)
    errors: List[str] = dataclass_field(default_factory=list)


@dataclass
class RenderState:
    ready: bool = False
    blockers: List[str] = dataclass_field(default_factory=list)
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
    changes: List[ToolChange] = dataclass_field(default_factory=list)
    validation: ValidationSnapshot = dataclass_field(default_factory=ValidationSnapshot)
    render_state: RenderState = dataclass_field(default_factory=RenderState)
    artifacts: List[ArtifactRef] = dataclass_field(default_factory=list)
    next_actions: List[str] = dataclass_field(default_factory=list)
    state: Dict[str, Any] = dataclass_field(default_factory=dict)
    decision: Dict[str, Any] = dataclass_field(default_factory=dict)
    payload: Any = None
    content: Any = None
    summary: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = dataclass_field(default_factory=utc_now)

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
