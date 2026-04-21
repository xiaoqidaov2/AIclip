"""协调器模式 - 任务编排的核心。"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .context import ContextManager
from .coordinator_impl import (
    ConcurrencyMode,
    CoordinatorExecutionMixin,
    CoordinatorPlanningMixin,
    CoordinatorStreamMixin,
    CoordinatorSummaryMixin,
    CoordinatorSynthesisMixin,
    CoordinatorWorkersMixin,
    WorkItem,
    WorkflowPhase,
)
from .notification import NotificationQueue
from .registry import TaskRegistry
from .verification import VerificationAgent
from .worker import WorkerManager


class CoordinatorMode(
    CoordinatorSummaryMixin,
    CoordinatorStreamMixin,
    CoordinatorSynthesisMixin,
    CoordinatorPlanningMixin,
    CoordinatorWorkersMixin,
    CoordinatorExecutionMixin,
):
    """协调器模式 — 四阶段工作流引擎。"""

    def __init__(
        self,
        agent: Any,
        tools: List[Any],
        task_registry: TaskRegistry,
        notification_queue: Optional[NotificationQueue] = None,
    ) -> None:
        self._agent = agent
        self._tools = tools
        self._registry = task_registry
        self._notifications = notification_queue or NotificationQueue()
        self._worker_mgr = WorkerManager(self._notifications)
        self._context_mgr = ContextManager()
        self._verification_agent = VerificationAgent(project_root=os.getcwd())
        self._current_phase = WorkflowPhase.RESEARCH
        self._phase_results: Dict[WorkflowPhase, List[Any]] = {
            phase: [] for phase in WorkflowPhase
        }

    async def run(self, user_request: str) -> Dict[str, Any]:
        research_items = self._plan_research(user_request)
        research_results = await self._execute_phase(
            WorkflowPhase.RESEARCH, research_items
        )
        self._phase_results[WorkflowPhase.RESEARCH] = research_results
        spec = await self._synthesize(user_request, research_results)
        self._phase_results[WorkflowPhase.SYNTHESIS] = [spec]
        impl_items = self._plan_implementation(spec)
        impl_results = await self._execute_phase(
            WorkflowPhase.IMPLEMENTATION, impl_items
        )
        self._phase_results[WorkflowPhase.IMPLEMENTATION] = impl_results
        verify_items = self._plan_verification(spec, impl_results)
        verify_results = await self._execute_phase(
            WorkflowPhase.VERIFICATION, verify_items
        )
        self._phase_results[WorkflowPhase.VERIFICATION] = verify_results
        return self._summarize()

    async def run_phase(
        self, phase: WorkflowPhase, items: List[WorkItem]
    ) -> List[Any]:
        return await self._execute_phase(phase, items)
