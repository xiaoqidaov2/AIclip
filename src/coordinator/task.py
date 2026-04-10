"""Task type and state definitions."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from typing import Any, Callable, Dict, Optional


class TaskType(str, Enum):
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

    def can_transition_to(self, target: TaskStatus) -> bool:
        return target in _TRANSITIONS.get(self, set())


_TRANSITIONS: Dict[TaskStatus, set] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.KILLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.KILLED: set(),
}


class TaskError(Exception):
    pass


@dataclass
class TaskInstance:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    task_type: TaskType = TaskType.LOCAL_AGENT
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def transition_to(self, target: TaskStatus) -> None:
        if not self.status.can_transition_to(target):
            raise TaskError(
                f"Illegal status transition {self.status.value} -> {target.value} (task={self.id})"
            )
        self.status = target
        now = time.time()
        if target == TaskStatus.RUNNING:
            self.started_at = now
        elif target in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED):
            self.finished_at = now

    def start(self) -> None:
        self.transition_to(TaskStatus.RUNNING)

    def complete(self, result: Any = None) -> None:
        self.result = result
        self.progress = 1.0
        self.transition_to(TaskStatus.COMPLETED)

    def fail(self, error: str) -> None:
        self.error = error
        self.transition_to(TaskStatus.FAILED)

    def kill(self) -> None:
        self.transition_to(TaskStatus.KILLED)

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)

    @property
    def elapsed(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at or time.time()
        return end - self.started_at


class Task(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def task_type(self) -> TaskType: ...

    @abstractmethod
    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        ...

    @abstractmethod
    async def kill(self, instance: TaskInstance) -> None:
        ...


class LocalBashTask(Task):
    name = "LocalBash"
    task_type = TaskType.LOCAL_BASH

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        import asyncio

        cmd = context.get("command", "")
        timeout = context.get("timeout", 30)
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TaskError(f"Command timed out ({timeout}s): {cmd}")
        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "returncode": proc.returncode,
        }

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
        args = context.get("args", ())
        kwargs = context.get("kwargs", {})
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class LocalWorkflowTask(Task):
    name = "LocalWorkflow"
    task_type = TaskType.LOCAL_WORKFLOW

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        steps = context.get("steps", [])
        results = []
        for i, step in enumerate(steps):
            instance.progress = i / max(len(steps), 1)
            results.append(step(context))
        return results

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


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
        prompt = context.get("prompt", "")
        return {"dream_prompt": prompt, "insight": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class RemoteAgentTask(Task):
    name = "RemoteAgent"
    task_type = TaskType.REMOTE_AGENT

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        endpoint = context.get("endpoint")
        payload = context.get("payload")
        return {"endpoint": endpoint, "payload": payload, "response": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()
