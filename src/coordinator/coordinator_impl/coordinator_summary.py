from __future__ import annotations

from typing import Any, Dict, List

from ..notification import TaskNotification, NotificationQueue
from ..worker import WorkerManager


class CoordinatorSummaryMixin:
    _context_mgr: Any
    _current_phase: Any
    _notifications: NotificationQueue
    _phase_results: Dict[Any, List[Any]]
    _worker_mgr: WorkerManager

    def _summarize(self) -> Dict[str, Any]:
        return {
            "phases": {phase.value: results for phase, results in self._phase_results.items()},
            "notifications": [n.to_xml() for n in self._notifications.history],
            "workers": [
                {"id": worker.id, "name": worker.name, "status": worker.status.value, "elapsed": worker.elapsed}
                for worker in self._worker_mgr.get_all_agents()
            ],
        }

    async def process_notifications(self) -> List[TaskNotification]:
        return await self._notifications.drain()

    @property
    def current_phase(self) -> Any:
        return self._current_phase

    @property
    def worker_manager(self) -> WorkerManager:
        return self._worker_mgr

    @property
    def context_manager(self) -> Any:
        return self._context_mgr

    @property
    def notification_queue(self) -> NotificationQueue:
        return self._notifications