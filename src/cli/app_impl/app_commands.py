from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from src.cli.commands import clear_history, show_detailed_status, show_help, show_status, toggle_verbose


class CLIAppCommandsMixin:
    history: list[Any]
    orchestrator: Any
    renderer: Any
    session_state: Any
    theme: Any
    tool_setup: Any
    _active_skill: Any
    _locked_skill: Any

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def run(self) -> None:
        print("AiClip CLI")
        print("输入 /help 查看命令，/exit 退出。")
        while True:
            try:
                user_input = input("AiClip> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见。")
                break
            self.handle_input(user_input)
            if getattr(self, "_should_exit", False):
                break

    def run_once(self, user_input: str) -> None:
        self.handle_input(user_input, interactive=False)

    def handle_input(self, user_input: str, interactive: bool = True) -> None:
        if not user_input:
            return
        if user_input in {"/exit", "/quit"}:
            if interactive:
                print("再见。")
            self._should_exit = True
            return
        if self._handle_builtin_command(user_input):
            return
        orchestration = self.orchestrator.plan(user_input, locked_skill=self._locked_skill)
        self._log_orchestration(orchestration)
        route = orchestration.route
        self.session_state.update_route_decision(
            {
                "skill_name": route.skill_name,
                "locked": route.locked,
                "matched_terms": route.matched_terms,
                "score": route.score,
                "reason": route.reason,
                "confidence": route.confidence,
            }
        )
        self.history.append(HumanMessage(content=user_input))
        self.session_state.add_stage_context(
            {
                "phase": "route",
                "summary": f"skill={route.skill_name} confidence={route.confidence:.2f} reason={route.reason}",
                "planner_mode": getattr(orchestration, "planner_mode", "unknown"),
                "allowed_tools": getattr(orchestration.steps[0], "allowed_tools", []) if orchestration.steps else [],
            }
        )
        try:
            print(self.theme.info(f"[pipeline] starting {getattr(orchestration, 'planner_mode', 'unknown')} plan"))
            self._run_orchestrated_steps(user_input, orchestration.steps, planner_mode=getattr(orchestration, "planner_mode", "unknown"))
            print(self.theme.info("[pipeline] done"))
        except Exception as e:
            self.renderer.clear_status()
            print(f"\nError: {e}")

    def _handle_builtin_command(self, user_input: str) -> bool:
        if user_input == "/help":
            show_help(self.tool_setup.get_skill_names())
        elif user_input == "/skills":
            self._show_skills()
        elif user_input.startswith("/skill "):
            self._set_skill(user_input[len("/skill ") :].strip())
        elif user_input == "/auto_skill":
            self._locked_skill = None
            print("Skill mode: auto")
        elif user_input == "/clear":
            self.history = []
            self.session_state.clear()
            self._locked_skill = None
            self._active_skill = None
            self._refresh_runtime()
            clear_history()
        elif user_input == "/verbose":
            self.renderer.set_verbose(toggle_verbose(self.renderer.verbose))
        elif user_input == "/plan":
            planner_skill = self.tool_setup.get_planner_skill_name()
            self._set_skill(planner_skill)
            self.orchestrator.enable_llm_plan = True
            print(self.theme.info(f"Plan skill activated: {planner_skill}"))
        elif user_input == "/status":
            show_detailed_status(
                verbose=self.renderer.verbose,
                active_skill=self.session_state.active_skill or self._locked_skill,
                locked_skill=self._locked_skill,
                planner_enabled=bool(getattr(self.orchestrator, "enable_llm_plan", False)),
                history_count=len(self.history),
                last_file_path=getattr(self.session_state, "last_file_path", None),
                last_tool_name=getattr(self.session_state, "last_tool_name", None),
            )
            self._print_session_state()
        else:
            return False
        return True

    def _show_skills(self) -> None:
        print("\nAvailable skills:")
        for skill_name in self.tool_setup.get_skill_names():
            skill = self.tool_setup.get_skill(skill_name)
            marker = " *" if self._locked_skill == skill_name else ""
            print(f"  {skill.name}{marker} - {skill.description}")
        print()

    def _set_skill(self, skill_name: str) -> None:
        try:
            skill = self.tool_setup.get_skill(skill_name)
        except KeyError as exc:
            available = ", ".join(self.tool_setup.get_skill_names())
            print(f"{exc}. Available skills: {available}")
            return
        self._locked_skill = skill.name
        self.session_state.active_skill = skill.name
        self._refresh_runtime(skill.name)
        print(f"Active skill: {skill.name}")
