from __future__ import annotations

import asyncio
import ast
import json
from typing import Any, Dict, List, Union

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.cli.commands import clear_history, show_help, show_status, toggle_verbose
from src.cli.render import CLIRenderer
from src.cli.state import SessionState


class CLIApp:
    def __init__(self, agent, coordinator=None):
        self.agent = agent
        self.coordinator = coordinator
        self.renderer = CLIRenderer()
        self.session_state = SessionState()
        self.history: List[Union[HumanMessage, AIMessage, ToolMessage]] = []

    def run(self) -> None:
        print("AiClip CLI")
        print("输入 /help 查看命令，/exit 退出。")

        while True:
            try:
                user_input = input("AiClip> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue

            if user_input in {"/exit", "/quit"}:
                print("再见！")
                break
            if user_input == "/help":
                show_help()
                continue
            if user_input == "/clear":
                self.history = []
                self.session_state.clear()
                clear_history()
                continue
            if user_input == "/verbose":
                self.renderer.set_verbose(toggle_verbose(self.renderer.verbose))
                continue
            if user_input == "/status":
                show_status(self.renderer.verbose)
                self._print_session_state()
                continue
            if user_input.startswith("/coordinate "):
                request = user_input[len("/coordinate ") :].strip()
                if request:
                    self._run_coordinator(request)
                else:
                    print("用法: /coordinate <任务描述>")
                continue
            if user_input == "/workers":
                self._show_workers()
                continue

            self.history.append(HumanMessage(content=user_input))

            try:
                self._run_agent()
            except Exception as e:
                self.renderer.clear_status()
                print(f"\nError: {e}")

    def _build_messages(self):
        messages = []
        if self.session_state.has_context:
            messages.append(SystemMessage(content=self.session_state.to_context_prompt()))
        messages.extend(self.history)
        return messages

    def _run_agent(self) -> None:
        """Run the agent with streaming if available, otherwise fallback to invoke."""
        self.renderer.show_status("思考中...")
        messages = self._build_messages()

        if hasattr(self.agent, "stream"):
            try:
                final_message, streamed_messages = self.renderer.render_stream(lambda: self.agent.stream({"messages": messages}))
                self._sync_session_state(streamed_messages)
                if streamed_messages:
                    self.history.extend(streamed_messages)
                if final_message:
                    print(f"\n{final_message}")
                return
            except Exception:
                pass

        response = self.agent.invoke({"messages": messages})
        final_message = self.renderer.render_response(response)
        response_messages = response.get("messages", []) if isinstance(response, dict) else []
        self._sync_session_state(response_messages)
        if response_messages:
            self.history.extend(response_messages)

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
        """通过协调器执行四阶段工作流。"""
        if self.coordinator is None:
            print("协调器未启用。")
            return

        self.renderer.show_status("协调器启动...")

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
        """Print coordinator notifications that arrived since the last flush."""
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
                print(f"\n└─ {summary}")
            elif summary.startswith("Worker ") and notification.status.value == "running":
                print(f"\n┌─ {summary}")
            else:
                print(f"\n└─ [{notification.status.value}] {summary}")

    def _show_workers(self) -> None:
        """显示当前所有 Worker 状态。"""
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
