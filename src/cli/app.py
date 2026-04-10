from typing import List, Dict, Any, Union, Optional
import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.cli.render import CLIRenderer
from src.cli.commands import show_help, clear_history, toggle_verbose, show_status


class CLIApp:
    def __init__(self, agent, coordinator=None):
        self.agent = agent
        self.coordinator = coordinator
        self.renderer = CLIRenderer()
        # history now stores real LangChain message objects
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
                clear_history()
                continue
            if user_input == "/verbose":
                self.renderer.set_verbose(toggle_verbose(self.renderer.verbose))
                continue
            if user_input == "/status":
                show_status(self.renderer.verbose)
                continue
            if user_input.startswith("/coordinate "):
                request = user_input[len("/coordinate "):].strip()
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
                final_message = self._run_agent()
                if final_message:
                    self.history.append(AIMessage(content=final_message))
            except Exception as e:
                self.renderer.clear_status()
                print(f"\nError: {e}")

    def _run_agent(self) -> str:
        """Run the agent with streaming if available, otherwise fallback to invoke."""
        self.renderer.show_status("思考中...")

        if hasattr(self.agent, "stream"):
            try:
                final_message, streamed_messages = self.renderer.render_stream(
                    self.agent.stream({"messages": self.history})
                )
                self.renderer.clear_status()

                if streamed_messages:
                    self.history.extend(streamed_messages)

                if final_message:
                    print(f"\n{final_message}")
                return final_message or ""
            except Exception:
                pass

        response = self.agent.invoke({"messages": self.history})
        final_message = self.renderer.render_response(response)
        if final_message:
            print(f"\n{final_message}")
        return final_message or ""

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
        """Run coordinator while flushing queued notifications in real time."""
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
            progress = f"{inst.progress*100:.0f}%"
            print(f"  {inst.name} [{inst.status.value}] 进度={progress} 耗时={elapsed}")
        print()
