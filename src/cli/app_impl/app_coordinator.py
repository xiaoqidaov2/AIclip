from __future__ import annotations

import asyncio
from typing import Any, Dict


class CLIAppCoordinatorMixin:
    coordinator: Any
    renderer: Any

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

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
        coordinator = self.coordinator
        if coordinator is None:
            raise RuntimeError("Coordinator runtime is not available")
        task = asyncio.create_task(coordinator.run(request))
        while not task.done():
            await self._flush_coordinator_notifications()
            await asyncio.sleep(0.15)
        await self._flush_coordinator_notifications()
        return await task

    async def _flush_coordinator_notifications(self) -> None:
        coordinator = self.coordinator
        if coordinator is None:
            return
        notifications = await coordinator.process_notifications()
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