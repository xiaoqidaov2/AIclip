from __future__ import annotations

from typing import Any, Dict

from .task_base import Task, TaskInstance, TaskType


class MonitorMCPTask(Task):
    name = "MonitorMCP"
    task_type = TaskType.MONITOR_MCP

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        return {"status": "monitoring", "target": context.get("target")}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class DreamTask(Task):
    name = "Dream"
    task_type = TaskType.DREAM

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        return {"dream_prompt": context.get("prompt", ""), "insight": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class RemoteAgentTask(Task):
    name = "RemoteAgent"
    task_type = TaskType.REMOTE_AGENT

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        return {"endpoint": context.get("endpoint"), "payload": context.get("payload"), "response": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()
