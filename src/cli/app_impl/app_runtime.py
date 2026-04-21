from __future__ import annotations

from typing import Any, Callable, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.cli.render import CLIRenderer
from src.cli.state import SessionState
from src.llm.query_orchestrator import QueryOrchestrator
from src.llm.skill_router import SkillRouter


class CLIAppRuntimeMixin:
    def __init__(
        self,
        agent_factory: Callable[[Optional[str]], Any],
        tool_setup: Any,
        llm_config: Any,
        coordinator_factory: Optional[Callable[[Any, Optional[str]], Any]] = None,
        initial_skill: Optional[str] = None,
        enable_llm_plan: bool = False,
    ) -> None:
        self.agent_factory = agent_factory
        self.tool_setup = tool_setup
        self.skill_router = SkillRouter(tool_setup, llm_config=llm_config)
        self.orchestrator = QueryOrchestrator(
            self.skill_router,
            tool_setup,
            llm_config=llm_config,
            enable_llm_plan=enable_llm_plan,
        )
        self.coordinator_factory = coordinator_factory
        self.agent = None
        self.coordinator = None
        self.renderer = CLIRenderer()
        self.theme = self.renderer.theme
        self.session_state = SessionState()
        self.history: List[Union[HumanMessage, AIMessage, ToolMessage]] = []
        self._locked_skill: Optional[str] = None
        self._active_skill: Optional[str] = None
        if initial_skill:
            self._locked_skill = initial_skill
            self.session_state.active_skill = initial_skill
        elif self.session_state.active_skill is None:
            self.session_state.active_skill = self.tool_setup.get_skill().name
        self._llm_log = self._build_llm_logger()
        self.skill_router._logger = self._llm_log
        self.orchestrator._logger = self._llm_log
        self._refresh_runtime()

    def _build_llm_logger(self) -> Any:
        def _logger(stage: str, message: str) -> None:
            if stage == "route":
                print(self.theme.info(f"[route] {message}"))
            elif stage == "plan":
                print(self.theme.info(f"[plan] {message}"))
            else:
                print(self.theme.muted(f"[{stage}] {message}"))

        return _logger

    def _resolve_skill_for_input(self, user_input: str) -> tuple[str, Any]:
        decision = self.skill_router.resolve(
            user_input,
            locked_skill=self._locked_skill,
            fallback_skill=self.tool_setup.get_skill().name,
        )
        return decision.skill_name, decision

    def _log_orchestration(self, result: Any) -> None:
        route = result.route
        print(
            self.theme.info(
                f"[orchestrator] planner={getattr(result, 'planner_mode', 'unknown')} "
                f"route skill={route.skill_name} confidence={route.confidence:.2f} "
                f"locked={route.locked} reason={route.reason}"
            )
        )
        print(
            self.theme.info(
                f"[orchestrator] discovered skills: {', '.join(result.steps[i].skill_name for i in range(len(result.steps)))}"
            )
        )
        if getattr(result, "raw_plan", None):
            print(
                self.theme.muted(
                    f"[orchestrator] raw_plan_keys={', '.join(sorted(result.raw_plan.keys()))}"
                )
            )
        for index, step in enumerate(result.steps, start=1):
            print(
                self.theme.muted(
                    f"[orchestrator] step {index}: phase={step.phase.value} skill={step.skill_name} reason={step.reason}"
                )
            )
            if step.allowed_tools:
                print(
                    self.theme.muted(
                        f"[orchestrator] step {index} allowed_tools: {', '.join(step.allowed_tools)}"
                    )
                )
            if step.stop_conditions:
                print(
                    self.theme.muted(
                        f"[orchestrator] step {index} stop_conditions: {', '.join(step.stop_conditions)}"
                    )
                )
        for nudge in result.nudges:
            print(self.theme.warn(f"[nudge] {nudge}"))

    def _refresh_runtime(self, skill_name: Optional[str] = None) -> None:
        resolved_skill = (
            skill_name
            or self._active_skill
            or self.session_state.active_skill
            or self.tool_setup.get_skill().name
        )
        self._active_skill = resolved_skill
        if self.session_state.active_skill is None:
            self.session_state.active_skill = resolved_skill
        tools = self.tool_setup.get_skill_tools(resolved_skill)
        tool_names = [getattr(tool, "__name__", type(tool).__name__) for tool in tools]
        print(
            self.theme.info(
                f"[skill] loading {resolved_skill} with {len(tool_names)} tool(s): {', '.join(tool_names)}"
            )
        )
        self.agent = self.agent_factory(resolved_skill)
        print(self.theme.success(f"[agent] ready for skill={resolved_skill}"))
        self.coordinator = (
            self.coordinator_factory(self.agent, resolved_skill)
            if self.coordinator_factory
            else None
        )
        if self.coordinator_factory:
            print(self.theme.success(f"[coordinator] ready for skill={resolved_skill}"))