"""任务终止机制 — 三重验证 + 中途纠偏。

终止流程：
1. 任务存在 → 2. 任务运行中 → 3. 任务类型支持终止
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from .task import TaskInstance, TaskStatus, Task, TaskError
from .registry import TaskRegistry


class StopTaskError(Exception):
    """任务终止失败。"""

    class Reason(str, Enum):
        NOT_FOUND = "not_found"
        NOT_RUNNING = "not_running"
        UNSUPPORTED_TYPE = "unsupported_type"

    def __init__(self, reason: Reason, task_id: Optional[str] = None):
        self.reason = reason
        self.task_id = task_id
        super().__init__(f"StopTask failed: {reason.value}" + (f" (task={task_id})" if task_id else ""))


async def stop_task(
    task_id: str,
    task_instance: Optional[TaskInstance],
    task_impl: Optional[Task],
    registry: TaskRegistry,
) -> None:
    """终止任务 — 三重验证。

    Args:
        task_id: 任务 ID
        task_instance: 任务实例（从 WorkerManager 获取）
        task_impl: 任务实现（从 TaskRegistry 获取）
        registry: 任务注册表

    Raises:
        StopTaskError: 终止失败
    """
    # 1. 任务存在
    if not task_instance:
        raise StopTaskError(StopTaskError.Reason.NOT_FOUND, task_id)

    # 2. 任务运行中
    if task_instance.status != TaskStatus.RUNNING:
        raise StopTaskError(StopTaskError.Reason.NOT_RUNNING, task_id)

    # 3. 任务类型支持终止
    if not task_impl:
        raise StopTaskError(StopTaskError.Reason.UNSUPPORTED_TYPE, task_id)

    # 执行终止
    await task_impl.kill(task_instance)


class TaskStopTool:
    """任务终止工具 — 供 Agent 调用。

    使用场景：
    - 发现方向错误 → 停止当前任务 → SendMessage 重定向
    - 用户取消请求
    - 超时强制终止
    """

    def __init__(self, registry: TaskRegistry):
        self._registry = registry

    async def __call__(self, task_id: str, instance: Optional[TaskInstance]) -> dict:
        """执行任务终止。

        Returns:
            {"success": True} 或 {"error": "原因"}
        """
        try:
            task_type = instance.task_type if instance else None
            task_impl = self._registry.get_task_by_type(task_type) if task_type else None

            await stop_task(task_id, instance, task_impl, self._registry)
            return {"success": True, "task_id": task_id}

        except StopTaskError as e:
            return {"success": False, "error": e.reason.value, "task_id": task_id}
        except Exception as e:
            return {"success": False, "error": str(e), "task_id": task_id}
