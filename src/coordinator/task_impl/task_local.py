from __future__ import annotations

from functools import partial
from typing import Any, Callable, Dict, Optional

from .task_base import Task, TaskError, TaskInstance, TaskType


class LocalBashTask(Task):
    name = "LocalBash"
    task_type = TaskType.LOCAL_BASH

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        import asyncio
        cmd = context.get("command", "")
        timeout = context.get("timeout", 30)
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TaskError(f"Command timed out ({timeout}s): {cmd}")
        return {"stdout": stdout.decode(errors="replace"), "stderr": stderr.decode(errors="replace"), "returncode": proc.returncode}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class LocalAgentTask(Task):
    name = "LocalAgent"
    task_type = TaskType.LOCAL_AGENT

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        raise NotImplementedError("LocalAgentTask.execute is driven by WorkerManager")

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class InProcessTeammateTask(Task):
    name = "InProcessTeammate"
    task_type = TaskType.IN_PROCESS_TEAMMATE

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        import asyncio
        func: Optional[Callable] = context.get("func")
        if func is None:
            raise TaskError("InProcessTeammate requires context['func']")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *context.get("args", ()), **context.get("kwargs", {})))

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class LocalWorkflowTask(Task):
    name = "LocalWorkflow"
    task_type = TaskType.LOCAL_WORKFLOW

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        steps = context.get("steps", [])
        results = []
        for index, step in enumerate(steps):
            instance.progress = index / max(len(steps), 1)
            results.append(step(context))
        return results

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()
