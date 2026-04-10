"""Notification queue for task status updates."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional

from .task import TaskInstance, TaskStatus


@dataclass
class TaskNotification:
    task_id: str
    status: TaskStatus
    summary: str = ""
    result: Any = None
    usage: Optional[Dict[str, Any]] = None

    def to_xml(self) -> str:
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
        return cls(
            task_id=instance.id,
            status=instance.status,
            summary=summary or f"Task {instance.name} {instance.status.value}",
            result=instance.result,
        )


class NotificationQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TaskNotification] = asyncio.Queue()
        self._history: List[TaskNotification] = []
        self._history_lock = Lock()

    def record_history(self, notification: TaskNotification) -> None:
        with self._history_lock:
            self._history.append(notification)

    async def enqueue(self, notification: TaskNotification) -> None:
        self.record_history(notification)
        await self._queue.put(notification)

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[TaskNotification]:
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    async def drain(self) -> List[TaskNotification]:
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
        with self._history_lock:
            return list(self._history)

    def clear_history(self) -> None:
        with self._history_lock:
            self._history.clear()
