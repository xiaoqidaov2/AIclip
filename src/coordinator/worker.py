"""Worker 管理 — 注册异步 Agent、追踪进度、标记完成/失败。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .task import TaskInstance, TaskStatus, TaskType, TaskError
from .notification import TaskNotification, NotificationQueue

logger = logging.getLogger(__name__)


class WorkerManager:
    """管理所有 Worker（子 Agent）的生命周期。

    关键功能：
    - register_async_agent()  注册异步 Agent 任务
    - complete_agent_task()   标记任务完成
    - fail_agent_task()       标记任务失败
    - update_agent_progress() 追踪任务进度
    - kill_agent()            终止 Agent
    """

    def __init__(self, notification_queue: NotificationQueue) -> None:
        self._agents: Dict[str, TaskInstance] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._notification_queue = notification_queue

    # ---- 注册 ----

    def register_async_agent(
        self,
        name: str,
        task_type: TaskType = TaskType.LOCAL_AGENT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TaskInstance:
        """注册一个新的异步 Agent 任务实例。"""
        instance = TaskInstance(
            name=name,
            task_type=task_type,
            metadata=metadata or {},
        )
        self._agents[instance.id] = instance
        logger.info("注册 Agent: %s (id=%s, type=%s)", name, instance.id, task_type.value)
        return instance

    # ---- 执行 ----

    async def run_agent(
        self,
        instance: TaskInstance,
        execute_fn: Callable[..., Any],
        context: Dict[str, Any],
    ) -> Any:
        """启动 Agent 执行并自动管理状态转移与通知。"""
        instance.start()
        logger.info("启动 Agent: %s (id=%s)", instance.name, instance.id)
        self._enqueue_sync(TaskNotification(
            task_id=instance.id,
            status=TaskStatus.RUNNING,
            summary=f"Worker {instance.name} 开始",
        ))

        try:
            if asyncio.iscoroutinefunction(execute_fn):
                result = await execute_fn(instance, context)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, execute_fn, instance, context)

            self.complete_agent_task(instance.id, result)
            return result

        except Exception as e:
            self.fail_agent_task(instance.id, str(e))
            raise

    def launch_agent(
        self,
        instance: TaskInstance,
        execute_fn: Callable[..., Any],
        context: Dict[str, Any],
    ) -> asyncio.Task:
        """以后台 asyncio.Task 方式启动 Agent（非阻塞）。"""
        task = asyncio.create_task(
            self.run_agent(instance, execute_fn, context),
            name=f"worker-{instance.id}",
        )
        self._running_tasks[instance.id] = task
        task.add_done_callback(lambda _: self._running_tasks.pop(instance.id, None))
        return task

    # ---- 状态管理 ----

    def complete_agent_task(self, task_id: str, result: Any = None, summary: str = "") -> None:
        """标记任务完成，推送通知。"""
        instance = self._get_instance(task_id)
        instance.complete(result)
        notification = TaskNotification.from_instance(
            instance, summary=summary or f"Worker {instance.name} 完成"
        )
        self._enqueue_sync(notification)
        logger.info("Agent 完成: %s (id=%s)", instance.name, task_id)

    def fail_agent_task(self, task_id: str, error: str) -> None:
        """标记任务失败，推送通知。"""
        instance = self._get_instance(task_id)
        instance.fail(error)
        notification = TaskNotification(
            task_id=task_id,
            status=TaskStatus.FAILED,
            summary=f"Worker {instance.name} 失败: {error}",
        )
        self._enqueue_sync(notification)
        logger.warning("Agent 失败: %s (id=%s): %s", instance.name, task_id, error)

    def update_agent_progress(self, task_id: str, progress: float) -> None:
        """更新任务进度 (0-1)。"""
        instance = self._get_instance(task_id)
        instance.progress = max(0.0, min(1.0, progress))

    async def kill_agent(self, task_id: str) -> None:
        """终止指定 Agent。"""
        instance = self._get_instance(task_id)

        # 取消 asyncio task
        running = self._running_tasks.get(task_id)
        if running and not running.done():
            running.cancel()
            try:
                await running
            except asyncio.CancelledError:
                pass

        if not instance.is_terminal:
            instance.kill()

        notification = TaskNotification(
            task_id=task_id,
            status=TaskStatus.KILLED,
            summary=f"Worker {instance.name} 已终止",
        )
        self._enqueue_sync(notification)
        logger.info("Agent 已终止: %s (id=%s)", instance.name, task_id)

    # ---- 查询 ----

    def get_agent(self, task_id: str) -> Optional[TaskInstance]:
        return self._agents.get(task_id)

    def get_running_agents(self) -> List[TaskInstance]:
        return [
            inst for inst in self._agents.values()
            if inst.status == TaskStatus.RUNNING
        ]

    def get_all_agents(self) -> List[TaskInstance]:
        return list(self._agents.values())

    # ---- 内部 ----

    def _get_instance(self, task_id: str) -> TaskInstance:
        instance = self._agents.get(task_id)
        if instance is None:
            raise TaskError(f"未知的 Agent: {task_id}")
        return instance

    def _enqueue_sync(self, notification: TaskNotification) -> None:
        """同步推送通知（在事件循环外也可安全调用）。"""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._notification_queue.enqueue(notification))
        except RuntimeError:
            # 没有运行中的事件循环，直接加到 history
            self._notification_queue._history.append(notification)
