from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Set


def _extract_result_text(result: Any, max_chars: int = 400) -> str:
    if isinstance(result, dict):
        decision = result.get("decision")
        if isinstance(decision, dict):
            parts = []
            for key in ("operation", "code", "status"):
                value = decision.get(key)
                if value not in (None, ""):
                    parts.append(str(value))
            state = decision.get("state")
            if isinstance(state, dict):
                for key in ("project_path", "output_path", "media_path", "final_path"):
                    value = state.get(key)
                    if value not in (None, ""):
                        parts.append(f"{key}={value}")
                        break
            next_actions = decision.get("next_actions") or []
            if next_actions:
                parts.append(f"next={','.join(map(str, next_actions[:3]))}")
            if parts:
                return " | ".join(parts)[:max_chars]
        if "messages" in result:
            parts = []
            for msg in result["messages"]:
                content = getattr(msg, "content", "")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
            return " | ".join(parts)[:max_chars]
        if "operation" in result and "status" in result:
            return f"{result['operation']} | {result['status']}"[:max_chars]
        if "code" in result:
            return str(result["code"])[:max_chars]
        if "content" in result:
            content = result["content"]
            if isinstance(content, dict) and content.get("operation") and content.get("status"):
                return f"{content['operation']} | {content['status']}"[:max_chars]
            return str(content)[:max_chars]
        if "error" in result:
            return f"[error] {result['error']}"
    if isinstance(result, str):
        text = result.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, dict):
                decision = parsed.get("decision")
                if isinstance(decision, dict):
                    parts = []
                    for key in ("operation", "code", "status"):
                        value = decision.get(key)
                        if value not in (None, ""):
                            parts.append(str(value))
                    if parts:
                        return " | ".join(parts)[:max_chars]
                if "operation" in parsed and "status" in parsed:
                    return f"{parsed['operation']} | {parsed['status']}"[:max_chars]
                if "code" in parsed:
                    return str(parsed["code"])[:max_chars]
                if "status" in parsed:
                    return str(parsed["status"])[:max_chars]
        return result[:max_chars]
    return str(result)[:max_chars]


logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class WorkflowPhase(str, Enum):
    RESEARCH = "research"
    SYNTHESIS = "synthesis"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"


class ConcurrencyMode(str, Enum):
    PARALLEL = "parallel"
    SERIAL_BY_FILE = "serial_by_file"
    REGION_PARALLEL = "region_parallel"


@dataclass
class WorkItem:
    description: str
    phase: WorkflowPhase
    target_files: Set[str] = field(default_factory=set)
    target_topics: Set[str] = field(default_factory=set)
    context: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    concurrency: ConcurrencyMode = ConcurrencyMode.PARALLEL


PHASE_CONCURRENCY: Dict[WorkflowPhase, ConcurrencyMode] = {
    WorkflowPhase.RESEARCH: ConcurrencyMode.PARALLEL,
    WorkflowPhase.SYNTHESIS: ConcurrencyMode.SERIAL_BY_FILE,
    WorkflowPhase.IMPLEMENTATION: ConcurrencyMode.SERIAL_BY_FILE,
    WorkflowPhase.VERIFICATION: ConcurrencyMode.REGION_PARALLEL,
}