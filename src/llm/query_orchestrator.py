from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import json

from langchain_core.messages import HumanMessage, SystemMessage

from .skill_router import SkillDecision, SkillRouter


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


class QueryOrchestrator:
    def __init__(
        self,
        skill_router: SkillRouter,
        tool_setup: Any,
        llm_config: Optional[Any] = None,
        logger: Optional[Any] = None,
        enable_llm_plan: bool = False,
    ) -> None:
        self.skill_router = skill_router
        self.tool_setup = tool_setup
        self.llm_config = llm_config
        self._logger = logger
        self.enable_llm_plan = enable_llm_plan

    def plan(self, user_input: str, locked_skill: Optional[str] = None) -> OrchestrationResult:
        route = self.skill_router.resolve(
            user_input,
            locked_skill=locked_skill,
            fallback_skill=self.tool_setup.get_skill().name,
        )

        llm_plan = self._llm_plan(user_input, route) if self.enable_llm_plan else None
        if llm_plan is not None:
            steps = self._plan_to_steps(user_input, route, llm_plan)
            nudges = self._build_nudges(user_input, steps)
            return OrchestrationResult(
                route=route,
                steps=steps,
                nudges=nudges,
                planner_mode="llm",
                raw_plan=llm_plan,
            )

        skills = self._discover_skills(user_input, route)
        steps = self._build_steps(user_input, skills, route)
        nudges = self._build_nudges(user_input, steps)
        return OrchestrationResult(route=route, steps=steps, nudges=nudges, planner_mode="heuristic")

    def compress(self, phase: OrchestrationPhase, state: Dict[str, Any]) -> CompressedContext:
        summary_parts: List[str] = []
        for key in (
            "operation",
            "code",
            "status",
            "skill_name",
            "project_path",
            "output_path",
            "media_path",
            "final_path",
        ):
            value = state.get(key)
            if value not in (None, ""):
                summary_parts.append(f"{key}={value}")

        next_actions = state.get("next_actions") or []
        if next_actions:
            summary_parts.append(f"next={', '.join(map(str, next_actions[:3]))}")

        if not summary_parts:
            summary_parts.append("no structured state")

        return CompressedContext(
            phase=phase,
            summary=" | ".join(summary_parts),
            active_skill=state.get("skill_name"),
            evidence=dict(state),
        )

    def _llm_plan(self, user_input: str, route: SkillDecision) -> Optional[Dict[str, Any]]:
        if self.llm_config is None:
            return None

        try:
            llm = self.llm_config.create_llm()
            skill_catalog = []
            for skill_name in self.tool_setup.get_skill_names():
                skill = self.tool_setup.get_skill(skill_name)
                skill_catalog.append(
                    {
                        "name": skill.name,
                        "title": skill.title,
                        "description": skill.description,
                        "tools": skill.tool_names,
                        "keywords": skill.keywords,
                    }
                )

            prompt = (
                "Create a structured multi-stage execution plan for the request.\n"
                "Return JSON only with keys: primary_skill, skills, steps, nudges.\n"
                "Each step must have: phase, skill_name, reason, prompt, input_focus, allowed_tools, stop_conditions.\n"
                "Valid phases: discovery, plan, execute, compress, nudge.\n"
                "Use only the available skill names.\n"
                f"Planner skill: {self.tool_setup.get_planner_skill_name()}\n"
                f"Route suggestion: {route.skill_name}\n"
                f"Request: {user_input}\n"
                f"Available skills: {json.dumps(skill_catalog, ensure_ascii=False)}"
            )
            if self._logger:
                self._logger("plan", "llm planner started")
            response: Any = llm.invoke([
                SystemMessage(content="You are a strict query planner and skill orchestrator."),
                HumanMessage(content=prompt),
            ])
            if self._logger:
                self._logger("plan", "llm planner finished")
            content = getattr(response, "content", response)
            if not isinstance(content, str):
                return None
            payload = json.loads(content)
            if not isinstance(payload, dict):
                return None
            if not isinstance(payload.get("steps"), list):
                return None
            return payload
        except Exception:
            return None

    def _discover_skills(self, user_input: str, route: SkillDecision) -> List[str]:
        if route.skill_name in self.tool_setup.get_skill_names():
            return [route.skill_name]
        return []

    def _plan_to_steps(self, user_input: str, route: SkillDecision, plan: Dict[str, Any]) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        raw_steps = plan.get("steps") or []
        available = set(self.tool_setup.get_skill_names())

        for raw in raw_steps:
            if not isinstance(raw, dict):
                continue
            skill_name = str(raw.get("skill_name") or route.skill_name)
            if skill_name not in available:
                continue

            phase_name = str(raw.get("phase") or OrchestrationPhase.EXECUTE.value)
            try:
                phase = OrchestrationPhase(phase_name)
            except ValueError:
                phase = OrchestrationPhase.EXECUTE

            steps.append(PlannedStep(
                phase=phase,
                skill_name=skill_name,
                reason=str(raw.get("reason") or "llm planned step"),
                prompt=str(raw.get("prompt") or "Handle the request for this stage."),
                input_text=str(raw.get("input_focus") or user_input),
                locked=route.locked,
                allowed_tools=[str(item) for item in (raw.get("allowed_tools") or []) if str(item)],
                stop_conditions=[str(item) for item in (raw.get("stop_conditions") or []) if str(item)],
                metadata={
                    "role": raw.get("role"),
                    "raw_phase": phase_name,
                },
            ))

        if not steps:
            skills = self._discover_skills(user_input, route)
            return self._build_steps(user_input, skills, route)

        if all(step.skill_name != route.skill_name for step in steps):
            steps.insert(0, PlannedStep(
                phase=OrchestrationPhase.PLAN,
                skill_name=route.skill_name,
                reason=route.reason or "router suggestion",
                prompt="Start from the routed skill and decide whether another stage is required.",
                input_text=user_input,
                locked=route.locked,
                allowed_tools=list(self.tool_setup.get_skill(route.skill_name).tool_names),
                stop_conditions=["Do not use tools outside the active skill."],
                metadata={"role": "route"},
            ))

        return steps

    def _build_steps(self, user_input: str, skills: List[str], route: SkillDecision) -> List[PlannedStep]:
        steps: List[PlannedStep] = []
        if skills:
            skill_name = skills[0]
            steps.append(PlannedStep(
                phase=OrchestrationPhase.EXECUTE,
                skill_name=skill_name,
                reason=route.reason or "routed skill",
                prompt="Handle the request with the routed skill and avoid selecting another skill unless the user explicitly asks for a different stage.",
                input_text=user_input,
                locked=route.locked,
                allowed_tools=list(self.tool_setup.get_skill(skill_name).tool_names),
                stop_conditions=["Use only the active skill tools."],
            ))

        if not steps:
            steps.append(PlannedStep(
                phase=OrchestrationPhase.EXECUTE,
                skill_name=route.skill_name,
                reason=route.reason or "default plan",
                prompt="Handle the request with the routed skill.",
                input_text=user_input,
                locked=route.locked,
                allowed_tools=list(self.tool_setup.get_skill(route.skill_name).tool_names),
                stop_conditions=["Use only the active skill tools."],
            ))

        return steps

    def _build_nudges(self, user_input: str, steps: List[PlannedStep]) -> List[str]:
        if len(steps) > 1:
            return ["Prefer sequential loading per stage: discover -> execute -> compress -> continue."]
        return []
