from __future__ import annotations

from typing import Any, Dict, List, Optional

from .query_orchestrator_clarification import build_clarification_bundle
from .query_orchestrator_helpers import build_nudges, build_steps, discover_skills, plan_to_steps
from .query_orchestrator_llm import llm_plan
from .query_orchestrator_types import CompressedContext, OrchestrationPhase, OrchestrationResult
from ..skill_router import SkillRouter


class QueryOrchestrator:
    def __init__(self, skill_router: SkillRouter, tool_setup: Any, llm_config: Optional[Any] = None, logger: Optional[Any] = None, enable_llm_plan: bool = False) -> None:
        self.skill_router = skill_router
        self.tool_setup = tool_setup
        self.llm_config = llm_config
        self._logger = logger
        self.enable_llm_plan = enable_llm_plan

    def plan(
        self,
        user_input: str,
        locked_skill: Optional[str] = None,
        session_context: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationResult:
        route = self.skill_router.resolve(user_input, locked_skill=locked_skill, fallback_skill=self.tool_setup.get_skill().name)
        plan_payload = llm_plan(user_input, route, self.tool_setup, self.llm_config, self._logger) if self.enable_llm_plan else None
        if plan_payload is not None:
            steps = plan_to_steps(user_input, route, plan_payload, self.tool_setup, session_context=session_context)
            clarification = build_clarification_bundle(plan_payload)
            return OrchestrationResult(
                route=route,
                steps=steps,
                nudges=build_nudges(steps),
                clarification=clarification,
                planner_mode="llm",
                raw_plan=plan_payload,
            )
        skills = discover_skills(user_input, route, self.tool_setup)
        steps = build_steps(user_input, skills, route, self.tool_setup, session_context=session_context)
        return OrchestrationResult(route=route, steps=steps, nudges=build_nudges(steps), planner_mode="heuristic")

    def compress(self, phase: OrchestrationPhase, state: Dict[str, Any]) -> CompressedContext:
        summary_parts: List[str] = []
        step_failed = state.get("step_failed", False)
        if step_failed:
            summary_parts.append("status=FAILED")
        for key in ("operation", "code", "status", "skill_name", "project_path", "output_path", "media_path", "final_path"):
            value = state.get(key)
            if value not in (None, ""):
                summary_parts.append(f"{key}={value}")
        next_actions = state.get("next_actions") or []
        if next_actions:
            summary_parts.append(f"next={', '.join(map(str, next_actions[:3]))}")
        if not summary_parts:
            summary_parts.append("no structured state")
        return CompressedContext(phase=phase, summary=" | ".join(summary_parts), active_skill=state.get("skill_name"), evidence=dict(state))
