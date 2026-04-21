from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


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

    def can_transition_to(self, target: "TaskStatus") -> bool:
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
            raise TaskError(f"Illegal status transition {self.status.value} -> {target.value} (task={self.id})")
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
        return (self.finished_at or time.time()) - self.started_at


class Task(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        raise NotImplementedError

    @abstractmethod
    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def kill(self, instance: TaskInstance) -> None:
        raise NotImplementedError
