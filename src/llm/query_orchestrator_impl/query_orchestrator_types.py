from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..skill_router import SkillDecision


class OrchestrationPhase(str, Enum):
    DISCOVERY = "discovery"
    PLAN = "plan"
    EXECUTE = "execute"
    COMPRESS = "compress"
    NUDGE = "nudge"


@dataclass
class PlannedStep:
    phase: OrchestrationPhase
    skill_name: str
    reason: str
    prompt: str
    input_text: str
    locked: bool = False
    allowed_tools: List[str] = field(default_factory=list)
    stop_conditions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompressedContext:
    phase: OrchestrationPhase
    summary: str
    active_skill: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationResult:
    route: SkillDecision
    steps: List[PlannedStep]
    compressed_contexts: List[CompressedContext] = field(default_factory=list)
    nudges: List[str] = field(default_factory=list)
    planner_mode: str = "heuristic"
    raw_plan: Dict[str, Any] = field(default_factory=dict)
