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

    def to_dict(self, *, compact: bool = True) -> Dict[str, Any]:
        data = asdict(self)
        if not compact:
            data["summary"] = self.summary or self.message
            data["content"] = self.content
            if not data.get("decision"):
                data["decision"] = {
                    "ok": self.ok,
                    "next_actions": list(self.next_actions),
                }
            return data

        # --- compact mode: strip low-value / redundant fields ---------------
        # Omit empty optional fields
        for key in ("entity", "content", "error"):
            if not data.get(key):
                del data[key]

        # Omit empty changes list
        if not data.get("changes"):
            del data["changes"]

        # validation: omit if passed with no warnings/errors
        v = data.get("validation")
        if v and v.get("passed") and not v.get("warnings") and not v.get("errors"):
            del data["validation"]

        # render_state: omit if ready with no blockers and no paths
        r = data.get("render_state")
        if (r and r.get("ready") and not r.get("blockers")
                and not r.get("preview_path") and not r.get("final_path")):
            del data["render_state"]

        # decision is redundant with ok + next_actions
        del data["decision"]

        # summary: omit when identical to message or empty
        summary_val = self.summary or self.message
        if summary_val == data.get("message"):
            del data["summary"]
        else:
            data["summary"] = summary_val

        # timestamp: low value for LLM context
        del data["timestamp"]

        # artifacts: strip null label/checksum
        artifacts = data.get("artifacts")
        if artifacts:
            for art in artifacts:
                for null_key in ("label", "checksum"):
                    if art.get(null_key) is None:
                        del art[null_key]

        # state: omit if empty
        if not data.get("state"):
            del data["state"]

        return data

    def to_json(self, *, compact: bool = True) -> str:
        return json.dumps(self.to_dict(compact=compact), ensure_ascii=False, default=str)
