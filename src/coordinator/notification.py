"""通知机制 — 任务结果以 <task-notification> XML 格式在协调器和 Worker 之间流转。"""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .task import TaskInstance, TaskStatus


@dataclass
class TaskNotification:
    """一条任务通知。"""
    task_id: str
    status: TaskStatus
    summary: str = ""
    result: Any = None
    usage: Optional[Dict[str, Any]] = None  # token 用量等

    def to_xml(self) -> str:
        """序列化为 <task-notification> XML 字符串。"""
        root = ET.Element("task-notification")
        ET.SubElement(root, "task-id").text = self.task_id
        ET.SubElement(root, "status").text = self.status.value
        ET.SubElement(root, "summary").text = self.summary

        if self.result is not None:
            result_el = ET.SubElement(root, "result")
            result_el.text = str(self.result)

        if self.usage:
            usage_el = ET.SubElement(root, "usage")
            for k, v in self.usage.items():
                ET.SubElement(usage_el, k).text = str(v)

        return ET.tostring(root, encoding="unicode")

    @classmethod
    def from_xml(cls, xml_str: str) -> TaskNotification:
        """从 XML 字符串反序列化。"""
        root = ET.fromstring(xml_str)
        task_id = root.findtext("task-id", "")
        status_val = root.findtext("status", "pending")
        summary = root.findtext("summary", "")
        result_el = root.find("result")
        result = result_el.text if result_el is not None else None

        usage: Optional[Dict[str, Any]] = None
        usage_el = root.find("usage")
        if usage_el is not None:
            usage = {child.tag: child.text for child in usage_el}

        return cls(
            task_id=task_id,
            status=TaskStatus(status_val),
            summary=summary,
            result=result,
            usage=usage,
        )

    @classmethod
    def from_instance(cls, instance: TaskInstance, summary: str = "") -> TaskNotification:
        """从 TaskInstance 创建通知。"""
        return cls(
            task_id=instance.id,
            status=instance.status,
            summary=summary or f"Task {instance.name} {instance.status.value}",
            result=instance.result,
        )


class NotificationQueue:
    """异步通知队列 — 解耦任务分发和结果收集。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[TaskNotification] = asyncio.Queue()
        self._history: List[TaskNotification] = []

    async def enqueue(self, notification: TaskNotification) -> None:
        """将通知推入队列。"""
        self._history.append(notification)
        await self._queue.put(notification)

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[TaskNotification]:
        """从队列取出一条通知，可设超时。"""
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    async def drain(self) -> List[TaskNotification]:
        """取出当前队列中所有通知（非阻塞）。"""
        notifications: List[TaskNotification] = []
        while not self._queue.empty():
            try:
                notifications.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return notifications

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    @property
    def history(self) -> List[TaskNotification]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history.clear()
