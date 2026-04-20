from __future__ import annotations

import asyncio
import ast
import json
from typing import Any, Callable, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.cli.commands import clear_history, show_help, show_status, toggle_verbose
from src.cli.render import CLIRenderer
from src.cli.state import SessionState
from src.llm.query_orchestrator import QueryOrchestrator, OrchestrationPhase
from src.llm.skill_router import SkillRouter


class CLIApp:
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

    def _build_llm_logger(self):
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
        print(self.theme.info(f"[orchestrator] discovered skills: {', '.join(result.steps[i].skill_name for i in range(len(result.steps)))}"))
        if getattr(result, "raw_plan", None):
            print(self.theme.muted(f"[orchestrator] raw_plan_keys={', '.join(sorted(result.raw_plan.keys()))}"))
        for index, step in enumerate(result.steps, start=1):
            print(
                self.theme.muted(
                    f"[orchestrator] step {index}: phase={step.phase.value} skill={step.skill_name} reason={step.reason}"
                )
            )
            if step.allowed_tools:
                print(self.theme.muted(f"[orchestrator] step {index} allowed_tools: {', '.join(step.allowed_tools)}"))
            if step.stop_conditions:
                print(self.theme.muted(f"[orchestrator] step {index} stop_conditions: {', '.join(step.stop_conditions)}"))
        for nudge in result.nudges:
            print(self.theme.warn(f"[nudge] {nudge}"))

    def _refresh_runtime(self, skill_name: Optional[str] = None) -> None:
        resolved_skill = skill_name or self._active_skill or self.session_state.active_skill or self.tool_setup.get_skill().name
        self._active_skill = resolved_skill
        if self.session_state.active_skill is None:
            self.session_state.active_skill = resolved_skill

        tools = self.tool_setup.get_skill_tools(resolved_skill)
        tool_names = [getattr(tool, "__name__", type(tool).__name__) for tool in tools]
        print(self.theme.info(f"[skill] loading {resolved_skill} with {len(tool_names)} tool(s): {', '.join(tool_names)}"))

        self.agent = self.agent_factory(resolved_skill)
        print(self.theme.success(f"[agent] ready for skill={resolved_skill}"))

        self.coordinator = self.coordinator_factory(self.agent, resolved_skill) if self.coordinator_factory else None
        if self.coordinator_factory:
            print(self.theme.success(f"[coordinator] ready for skill={resolved_skill}"))

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

    def run_once(self, user_input: str) -> None:
        self.handle_input(user_input, interactive=False)

    def handle_input(self, user_input: str, interactive: bool = True) -> None:
        if not user_input:
            return

        if user_input in {"/exit", "/quit"}:
            if interactive:
                print("再见。")
            return
        if user_input == "/help":
            show_help(self.tool_setup.get_skill_names())
            return
        if user_input == "/skills":
            self._show_skills()
            return
        if user_input.startswith("/skill "):
            self._set_skill(user_input[len("/skill ") :].strip())
            return
        if user_input == "/auto_skill":
            self._locked_skill = None
            print("Skill mode: auto")
            return
        if user_input == "/clear":
            self.history = []
            self.session_state.clear()
            self._locked_skill = None
            self._active_skill = None
            self._refresh_runtime()
            clear_history()
            return
        if user_input == "/verbose":
            self.renderer.set_verbose(toggle_verbose(self.renderer.verbose))
            return
        if user_input == "/plan":
            planner_skill = self.tool_setup.get_planner_skill_name()
            self._set_skill(planner_skill)
            self.orchestrator.enable_llm_plan = True
            print(self.theme.info(f"Plan skill activated: {planner_skill}"))
            return
        if user_input == "/status":
            show_status(self.renderer.verbose)
            self._print_session_state()
            return
        if user_input.startswith("/coordinate "):
            request = user_input[len("/coordinate ") :].strip()
            if request:
                self._run_coordinator(request)
            else:
                print("用法: /coordinate <任务描述>")
            return
        if user_input == "/workers":
            self._show_workers()
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

    def _build_messages(self, extra_messages: Optional[List[Any]] = None):
        messages = []
        if self.session_state.has_context:
            messages.append(SystemMessage(content=self.session_state.to_context_prompt()))
        messages.extend(self.history)
        if extra_messages:
            messages.extend(extra_messages)
        return messages

    def _run_agent(self, extra_messages: Optional[List[Any]] = None, persist_history: bool = True) -> None:
        if self.agent is None:
            self._refresh_runtime(self.session_state.active_skill)

        self.renderer.show_status("Thinking...")
        messages = self._build_messages(extra_messages)

        if hasattr(self.agent, "stream"):
            try:
                final_message, streamed_messages = self.renderer.render_stream(lambda: self.agent.stream({"messages": messages}))
                self._sync_session_state(streamed_messages)
                if streamed_messages and persist_history:
                    self.history.extend(streamed_messages)
                if final_message:
                    print(f"\n{final_message}")
                return
            except Exception:
                pass

        response = self.agent.invoke({"messages": messages})
        _ = self.renderer.render_response(response)
        response_messages = response.get("messages", []) if isinstance(response, dict) else []
        self._sync_session_state(response_messages)
        if response_messages and persist_history:
            self.history.extend(response_messages)

        compressed = self.orchestrator.compress(
            OrchestrationPhase.EXECUTE,
            {
                "skill_name": self.session_state.active_skill,
                "operation": self.session_state.last_operation,
                "code": (self.session_state.last_decision or {}).get("code"),
                "status": (self.session_state.last_decision or {}).get("status"),
                "project_path": (self.session_state.last_decision or {}).get("state", {}).get("project_path") if self.session_state.last_decision else None,
                "output_path": (self.session_state.last_decision or {}).get("state", {}).get("output_path") if self.session_state.last_decision else None,
                "media_path": (self.session_state.last_decision or {}).get("state", {}).get("media_path") if self.session_state.last_decision else None,
                "final_path": (self.session_state.last_decision or {}).get("state", {}).get("final_path") if self.session_state.last_decision else None,
                "next_actions": (self.session_state.last_decision or {}).get("next_actions", []),
            },
        )
        self.session_state.last_route_decision = {
            **(self.session_state.last_route_decision or {}),
            "compressed_context": compressed.summary,
        }
        self.session_state.add_stage_context({"phase": "execute", "summary": compressed.summary})
        print(self.theme.info(f"[context] compressed: {compressed.summary}"))

    def _run_orchestrated_steps(self, user_input: str, steps: List[Any], planner_mode: str = "unknown") -> None:
        if not steps:
            self._run_agent()
            return

        for index, step in enumerate(steps, start=1):
            if step.skill_name != self._active_skill:
                self._refresh_runtime(step.skill_name)
            self.session_state.active_skill = step.skill_name
            print(
                self.theme.info(
                    f"[stage] {index}/{len(steps)} phase={step.phase.value} skill={step.skill_name} reason={step.reason}"
                )
            )

            stage_message = f"{step.prompt}\n\nUser request: {step.input_text}"
            if step.metadata:
                stage_message += f"\nStage metadata: {json.dumps(step.metadata, ensure_ascii=False)}"

            self._run_agent(extra_messages=[HumanMessage(content=stage_message)], persist_history=True)

            compressed = self.orchestrator.compress(
                step.phase,
                {
                    "skill_name": self.session_state.active_skill,
                    "operation": self.session_state.last_operation,
                    "code": (self.session_state.last_decision or {}).get("code"),
                    "status": (self.session_state.last_decision or {}).get("status"),
                    "project_path": (self.session_state.last_decision or {}).get("state", {}).get("project_path") if self.session_state.last_decision else None,
                    "output_path": (self.session_state.last_decision or {}).get("state", {}).get("output_path") if self.session_state.last_decision else None,
                    "media_path": (self.session_state.last_decision or {}).get("state", {}).get("media_path") if self.session_state.last_decision else None,
                    "final_path": (self.session_state.last_decision or {}).get("state", {}).get("final_path") if self.session_state.last_decision else None,
                    "next_actions": (self.session_state.last_decision or {}).get("next_actions", []),
                },
            )
            self.session_state.add_stage_context(
                {
                    "phase": step.phase.value,
                    "skill": step.skill_name,
                    "summary": compressed.summary,
                    "planner_mode": planner_mode,
                    "allowed_tools": step.allowed_tools,
                }
            )
            print(self.theme.info(f"[context] {step.phase.value} compressed: {compressed.summary}"))

    def _sync_session_state(self, messages: List[Any]) -> None:
        pending_tool_calls: List[Dict[str, Any]] = []

        for msg in messages:
            if isinstance(msg, AIMessage):
                tool_calls = getattr(msg, "tool_calls", None) or []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        pending_tool_calls.append(tool_call)
                continue

            if not isinstance(msg, ToolMessage):
                continue

            call = pending_tool_calls.pop(0) if pending_tool_calls else {}
            tool_name = getattr(msg, "name", None) or call.get("name", "tool")
            tool_args = call.get("args") if isinstance(call, dict) else None
            result = self._parse_tool_result(getattr(msg, "content", ""))
            self.session_state.update_from_tool(tool_name, result, tool_args)
            allowed_tools = []
            if self.session_state.last_route_decision:
                allowed_tools = self.session_state.last_route_decision.get("allowed_tools", []) or []
            self.session_state.add_stage_audit(
                {
                    "skill": self.session_state.active_skill,
                    "tool": tool_name,
                    "allowed_tools": allowed_tools,
                    "allowed": not allowed_tools or tool_name in allowed_tools,
                }
            )
            if allowed_tools and tool_name not in allowed_tools:
                print(self.theme.warn(f"[audit] blocked-or-offlist tool={tool_name} skill={self.session_state.active_skill} allowed={', '.join(allowed_tools)}"))

    def _parse_tool_result(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, dict):
            return content
        if content is None:
            return {}
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return {}
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {"content": parsed}
            except (json.JSONDecodeError, TypeError):
                try:
                    parsed = ast.literal_eval(text)
                    return parsed if isinstance(parsed, dict) else {"content": parsed}
                except (ValueError, SyntaxError):
                    return {"content": text}
        return {"content": content}

    def _print_session_state(self) -> None:
        print("\nSession state:")
        print(self.session_state.to_context_prompt())

    def _run_coordinator(self, request: str) -> None:
        if self.coordinator is None:
            print("协调器未启用。")
            return

        self.renderer.show_status("Coordinator starting...")

        try:
            asyncio.run(self._run_coordinator_async(request))
            self.renderer.clear_status()
        except Exception as e:
            self.renderer.clear_status()
            print(f"\n协调器错误: {e}")

    async def _run_coordinator_async(self, request: str) -> Dict[str, Any]:
        task = asyncio.create_task(self.coordinator.run(request))

        while not task.done():
            await self._flush_coordinator_notifications()
            await asyncio.sleep(0.15)

        await self._flush_coordinator_notifications()
        return await task

    async def _flush_coordinator_notifications(self) -> None:
        notifications = await self.coordinator.process_notifications()
        if not notifications:
            return

        for notification in notifications:
            summary = notification.summary
            if summary.startswith("进入阶段:"):
                phase_name = summary.split(":", 1)[1].strip()
                print(f"\n{'=' * 40}")
                print(f"阶段: {phase_name}")
                print(f"{'=' * 40}")
            elif summary.startswith("阶段完成:"):
                print(f"\n-> {summary}")
            elif summary.startswith("Worker ") and notification.status.value == "running":
                print(f"\n* {summary}")
            else:
                print(f"\n- [{notification.status.value}] {summary}")

    def _show_workers(self) -> None:
        if self.coordinator is None:
            print("协调器未启用。")
            return

        agents = self.coordinator.worker_manager.get_all_agents()
        if not agents:
            print("暂无 Worker。")
            return

        print(f"\n--- Workers ({len(agents)}) ---")
        for inst in agents:
            elapsed = f"{inst.elapsed:.1f}s" if inst.elapsed else "-"
            progress = f"{inst.progress * 100:.0f}%"
            print(f"  {inst.name} [{inst.status.value}] 进度={progress} 耗时={elapsed}")
        print()

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
            print(str(exc))
            return

        self._locked_skill = skill.name
        self.session_state.active_skill = skill.name
        self._refresh_runtime(skill.name)
        print(f"Active skill: {skill.name}")
