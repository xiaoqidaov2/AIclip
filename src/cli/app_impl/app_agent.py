from __future__ import annotations

import json
from typing import Any, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from src.llm.query_orchestrator import OrchestrationPhase


MAX_HISTORY_MESSAGES = 40


class CLIAppAgentMixin:
    agent: Any
    history: List[Any]
    orchestrator: Any
    renderer: Any
    session_state: Any
    theme: Any
    _active_skill: Any

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _build_messages(self, extra_messages: Optional[List[Any]] = None) -> List[Any]:
        messages: List[Any] = []
        if self.session_state.has_context:
            messages.append(SystemMessage(content=self.session_state.to_context_prompt()))
        messages.extend(self._trimmed_history())
        if extra_messages:
            messages.extend(extra_messages)
        return messages

    def _trimmed_history(self) -> List[Any]:
        if len(self.history) <= MAX_HISTORY_MESSAGES:
            return list(self.history)
        return list(self.history[-MAX_HISTORY_MESSAGES:])

    def _run_agent(
        self, extra_messages: Optional[List[Any]] = None, persist_history: bool = True
    ) -> None:
        if self.agent is None:
            self._refresh_runtime(self.session_state.active_skill)
        agent = self.agent
        if agent is None:
            raise RuntimeError("Agent runtime is not available")
        self.renderer.show_status("Thinking...")
        messages = self._build_messages(extra_messages)
        if hasattr(agent, "stream"):
            try:
                final_message, streamed_messages = self.renderer.render_stream(
                    lambda: agent.stream({"messages": messages})
                )
                self._sync_session_state(streamed_messages)
                if streamed_messages and persist_history:
                    self.history.extend(streamed_messages)
                    self.history = self._trimmed_history()
                if final_message:
                    print(f"\n{final_message}")
                return
            except Exception:
                pass
        response = agent.invoke({"messages": messages})
        _ = self.renderer.render_response(response)
        response_messages = response.get("messages", []) if isinstance(response, dict) else []
        self._sync_session_state(response_messages)
        if response_messages and persist_history:
            self.history.extend(response_messages)
            self.history = self._trimmed_history()
        compressed = self._compress_execution_context(OrchestrationPhase.EXECUTE)
        self.session_state.last_route_decision = {
            **(self.session_state.last_route_decision or {}),
            "compressed_context": compressed.summary,
        }
        self.session_state.add_stage_context({"phase": "execute", "summary": compressed.summary})
        print(self.theme.info(f"[context] compressed: {compressed.summary}"))

    def _run_orchestrated_steps(
        self, user_input: str, steps: List[Any], planner_mode: str = "unknown"
    ) -> None:
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
            compressed = self._compress_execution_context(step.phase)
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

    def _compress_execution_context(self, phase: Any) -> Any:
        decision = self.session_state.last_decision or {}
        state = decision.get("state", {}) if self.session_state.last_decision else {}
        return self.orchestrator.compress(
            phase,
            {
                "skill_name": self.session_state.active_skill,
                "operation": self.session_state.last_operation,
                "code": decision.get("code"),
                "status": decision.get("status"),
                "project_path": state.get("project_path"),
                "output_path": state.get("output_path"),
                "media_path": state.get("media_path"),
                "final_path": state.get("final_path"),
                "next_actions": decision.get("next_actions", []),
            },
        )