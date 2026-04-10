"""任务类型系统 - 定义任务类型、状态机和统一 Task 接口。

任务状态机: pending → running → completed/failed/killed
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class TaskType(str, Enum):
    """7 种任务类型。"""
    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(str, Enum):
    """任务状态机。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"

    # ------ 合法状态转移 ------
    _transitions: dict  # type hint only, actual stored on class

    def can_transition_to(self, target: TaskStatus) -> bool:
        return target in _TRANSITIONS.get(self, set())


_TRANSITIONS: Dict[TaskStatus, set] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.KILLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED},
    # 终态不可再转移
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.KILLED: set(),
}


class TaskError(Exception):
    """任务操作异常。"""


@dataclass
class TaskInstance:
    """一个具体的任务实例（运行态）。"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    task_type: TaskType = TaskType.LOCAL_AGENT
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    progress: float = 0.0          # 0-1
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---- 状态转移 ----
    def transition_to(self, target: TaskStatus) -> None:
        if not self.status.can_transition_to(target):
            raise TaskError(
                f"非法状态转移: {self.status.value} → {target.value} (task={self.id})"
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
    """统一的 Task 接口 — 每种 TaskType 对应一个实现。"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def task_type(self) -> TaskType: ...

    @abstractmethod
    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        """执行任务，返回结果。"""
        ...

    @abstractmethod
    async def kill(self, instance: TaskInstance) -> None:
        """终止正在运行的任务。"""
        ...


# ======================= 内置 Task 实现 =======================

class LocalBashTask(Task):
    """本地 Shell 命令任务。"""
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
            raise TaskError(f"命令超时 ({timeout}s): {cmd}")
        return {
            "stdout": stdout.decode(errors="replace"),
            "stderr": stderr.decode(errors="replace"),
            "returncode": proc.returncode,
        }

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class LocalAgentTask(Task):
    """本地 Agent 子任务 — 协调器 spawn 的 worker。"""
    name = "LocalAgent"
    task_type = TaskType.LOCAL_AGENT

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        # Worker 执行逻辑由 coordinator 和 worker 模块驱动
        # 这里只定义接口，实际调用在 worker.py
        raise NotImplementedError("LocalAgentTask.execute 由 WorkerManager 驱动")

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class InProcessTeammateTask(Task):
    """进程内协作任务（同步执行，共享内存）。"""
    name = "InProcessTeammate"
    task_type = TaskType.IN_PROCESS_TEAMMATE

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        func: Optional[Callable] = context.get("func")
        if func is None:
            raise TaskError("InProcessTeammate 需要 context['func']")
        args = context.get("args", ())
        kwargs = context.get("kwargs", {})
        return func(*args, **kwargs)

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class LocalWorkflowTask(Task):
    """本地工作流脚本任务。"""
    name = "LocalWorkflow"
    task_type = TaskType.LOCAL_WORKFLOW

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        steps = context.get("steps", [])
        results = []
        for i, step in enumerate(steps):
            instance.progress = i / max(len(steps), 1)
            result = step(context)
            results.append(result)
        return results

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class MonitorMCPTask(Task):
    """MCP 监控任务。"""
    name = "MonitorMCP"
    task_type = TaskType.MONITOR_MCP

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        # 占位 — 后续对接 MCP 协议
        return {"status": "monitoring", "target": context.get("target")}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class DreamTask(Task):
    """后台推理 / 反思任务。"""
    name = "Dream"
    task_type = TaskType.DREAM

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        prompt = context.get("prompt", "")
        # 占位 — 可对接低优先级 LLM 调用
        return {"dream_prompt": prompt, "insight": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()


class RemoteAgentTask(Task):
    """远程 Agent 任务（通过 HTTP/gRPC 调用）。"""
    name = "RemoteAgent"
    task_type = TaskType.REMOTE_AGENT

    async def execute(self, instance: TaskInstance, context: Dict[str, Any]) -> Any:
        # 占位 — 后续对接远程 Agent 协议
        endpoint = context.get("endpoint")
        payload = context.get("payload")
        return {"endpoint": endpoint, "payload": payload, "response": None}

    async def kill(self, instance: TaskInstance) -> None:
        instance.kill()
