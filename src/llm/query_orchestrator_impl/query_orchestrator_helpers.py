from __future__ import annotations

from typing import Any, Dict, List

from .query_orchestrator_types import OrchestrationPhase, PlannedStep
from ..skill_router import SkillDecision


def discover_skills(route: SkillDecision, tool_setup: Any) -> List[str]:
    if route.skill_name in tool_setup.get_skill_names():
        return [route.skill_name]
    return []


def build_steps(user_input: str, skills: List[str], route: SkillDecision, tool_setup: Any) -> List[PlannedStep]:
    steps: List[PlannedStep] = []
    if skills:
        skill_name = skills[0]
        steps.append(PlannedStep(phase=OrchestrationPhase.EXECUTE, skill_name=skill_name, reason=route.reason or "routed skill", prompt="Handle the request with the routed skill and avoid selecting another skill unless the user explicitly asks for a different stage.", input_text=user_input, locked=route.locked, allowed_tools=list(tool_setup.get_skill(skill_name).tool_names), stop_conditions=["Use only the active skill tools."]))
    if not steps:
        steps.append(PlannedStep(phase=OrchestrationPhase.EXECUTE, skill_name=route.skill_name, reason=route.reason or "default plan", prompt="Handle the request with the routed skill.", input_text=user_input, locked=route.locked, allowed_tools=list(tool_setup.get_skill(route.skill_name).tool_names), stop_conditions=["Use only the active skill tools."]))
    return steps


def plan_to_steps(user_input: str, route: SkillDecision, plan: Dict[str, Any], tool_setup: Any) -> List[PlannedStep]:
    steps: List[PlannedStep] = []
    available = set(tool_setup.get_skill_names())
    for raw in plan.get("steps") or []:
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
        steps.append(PlannedStep(phase=phase, skill_name=skill_name, reason=str(raw.get("reason") or "llm planned step"), prompt=str(raw.get("prompt") or "Handle the request for this stage."), input_text=str(raw.get("input_focus") or user_input), locked=route.locked, allowed_tools=[str(item) for item in (raw.get("allowed_tools") or []) if str(item)], stop_conditions=[str(item) for item in (raw.get("stop_conditions") or []) if str(item)], metadata={"role": raw.get("role"), "raw_phase": phase_name}))
    if not steps:
        return build_steps(user_input, discover_skills(route, tool_setup), route, tool_setup)
    if all(step.skill_name != route.skill_name for step in steps):
        steps.insert(0, PlannedStep(phase=OrchestrationPhase.PLAN, skill_name=route.skill_name, reason=route.reason or "router suggestion", prompt="Start from the routed skill and decide whether another stage is required.", input_text=user_input, locked=route.locked, allowed_tools=list(tool_setup.get_skill(route.skill_name).tool_names), stop_conditions=["Do not use tools outside the active skill."], metadata={"role": "route"}))
    return steps


def build_nudges(steps: List[PlannedStep]) -> List[str]:
    if len(steps) > 1:
        return ["Prefer sequential loading per stage: discover -> execute -> compress -> continue."]
    return []
