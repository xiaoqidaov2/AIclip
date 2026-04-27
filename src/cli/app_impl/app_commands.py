from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from src.cli.commands import clear_history, show_detailed_status, show_help, toggle_verbose


class CLIAppCommandsMixin:
    history: list[Any]
    orchestrator: Any
    renderer: Any
    session_state: Any
    theme: Any
    tool_setup: Any
    _active_skill: Any
    _locked_skill: Any
    _pending_orchestration: Any
    _pending_input: str | None

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def run(self) -> None:
        print("AiClip CLI")
        print("Enter /help for commands, /exit to quit.")
        while True:
            try:
                user_input = input("AiClip> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
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
                print("Bye.")
            self._should_exit = True
            return
        if self._handle_builtin_command(user_input):
            return
        self._execute_user_request(user_input)

    def _execute_user_request(self, user_input: str, preview_only: bool = False) -> None:
        original_plan_mode = bool(getattr(self.orchestrator, "enable_llm_plan", False))
        if preview_only:
            self.orchestrator.enable_llm_plan = True
        try:
            orchestration = self.orchestrator.plan(
                user_input,
                locked_skill=self._locked_skill,
                session_context=self._build_orchestration_context(),
            )
        finally:
            self.orchestrator.enable_llm_plan = original_plan_mode
        self._log_orchestration(orchestration)
        self._pending_orchestration = orchestration if preview_only else None
        self._pending_input = user_input if preview_only else None
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
        if getattr(orchestration, "clarification", None) is not None:
            self._render_clarification(orchestration.clarification)
            return
        if preview_only:
            print(self.theme.info(f"[pipeline] plan ready: {getattr(orchestration, 'planner_mode', 'unknown')}"))
            return
        print(self.theme.info(f"[pipeline] executing: {getattr(orchestration, 'planner_mode', 'unknown')}"))
        self._run_orchestrated_steps(
            user_input,
            orchestration.steps,
            planner_mode=getattr(orchestration, "planner_mode", "unknown"),
        )
        print(self.theme.info("[pipeline] done"))

    def _run_pending_plan(self) -> None:
        orchestration = getattr(self, "_pending_orchestration", None)
        if orchestration is None:
            print(self.theme.warn("No pending plan to execute."))
            return
        user_input = getattr(self, "_pending_input", "") or ""
        try:
            print(self.theme.info(f"[pipeline] executing pending plan: {getattr(orchestration, 'planner_mode', 'unknown')}"))
            self._run_orchestrated_steps(
                user_input,
                orchestration.steps,
                planner_mode=getattr(orchestration, "planner_mode", "unknown"),
            )
            print(self.theme.info("[pipeline] done"))
            self._pending_orchestration = None
            self._pending_input = None
        except Exception as e:
            self.renderer.clear_status()
            print(f"\nError: {e}")

    def _render_clarification(self, clarification: Any) -> None:
        print(self.theme.warn(f"[clarify] {clarification.reason}"))
        for index, question in enumerate(getattr(clarification, "questions", []), start=1):
            print(f"{index}. {question.prompt}")
            for choice in question.choices:
                detail = f" - {choice.description}" if choice.description else ""
                print(f"   - {choice.label}{detail}")
            print(f"   - {question.free_text_label}")

    def _build_orchestration_context(self) -> dict[str, Any]:
        decision = self.session_state.last_decision or {}
        state = decision.get("state", {}) if isinstance(decision.get("state"), dict) else {}
        render_state = self.session_state.last_render_state or {}
        return {
            "project_path": state.get("project_path"),
            "output_path": state.get("output_path"),
            "media_path": state.get("media_path"),
            "final_path": state.get("final_path") or render_state.get("final_path"),
            "preview_path": state.get("preview_path") or render_state.get("preview_path"),
            "short_video_score": self.session_state.last_short_video_score,
            "short_video_diagnosis": list(self.session_state.last_short_video_diagnosis),
            "last_operation": self.session_state.last_operation,
            "last_file_path": self.session_state.last_file_path,
        }

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
            self._pending_orchestration = None
            self._pending_input = None
            self.orchestrator.enable_llm_plan = False
            clear_history()
        elif user_input == "/verbose":
            self.renderer.set_verbose(toggle_verbose(self.renderer.verbose))
        elif user_input == "/plan":
            print(self.theme.warn("Usage: /plan <request>"))
        elif user_input.startswith("/plan "):
            self._execute_user_request(user_input[len("/plan ") :].strip(), preview_only=True)
        elif user_input in {"/run", "/execute"}:
            self._run_pending_plan()
        elif user_input == "/status":
            show_detailed_status(
                verbose=self.renderer.verbose,
                active_skill=self.session_state.active_skill or self._locked_skill,
                locked_skill=self._locked_skill,
                planner_enabled=bool(getattr(self.orchestrator, "enable_llm_plan", False)),
                history_count=len(self.history),
                last_file_path=getattr(self.session_state, "last_file_path", None),
                last_tool_name=getattr(self.session_state, "last_tool_name", None),
                has_pending_plan=bool(self._pending_orchestration),
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
