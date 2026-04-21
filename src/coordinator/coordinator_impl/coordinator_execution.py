from __future__ import annotations

import asyncio
from typing import Any, List

from .coordinator_models import ConcurrencyMode, PHASE_CONCURRENCY, WorkItem, WorkflowPhase, logger
from ..notification import TaskNotification
from ..task import TaskStatus


class CoordinatorExecutionMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    async def _execute_phase(self, phase: WorkflowPhase, items: List[WorkItem]) -> List[Any]:
        self._current_phase = phase
        default_concurrency = PHASE_CONCURRENCY[phase]
        logger.info("进入阶段: %s (%d 个工作单元)", phase.value, len(items))
        await self._notifications.enqueue(TaskNotification(task_id="coordinator", status=TaskStatus.RUNNING, summary=f"进入阶段: {phase.value}"))
        if not items:
            await self._notifications.enqueue(TaskNotification(task_id="coordinator", status=TaskStatus.COMPLETED, summary=f"阶段完成: {phase.value}"))
            return []
        for item in items:
            if item.concurrency == ConcurrencyMode.PARALLEL:
                item.concurrency = default_concurrency
        if default_concurrency == ConcurrencyMode.PARALLEL:
            results = await self._run_parallel(items)
        elif default_concurrency == ConcurrencyMode.SERIAL_BY_FILE:
            results = await self._run_serial_by_file(items)
        else:
            results = await self._run_region_parallel(items)
        await self._notifications.enqueue(TaskNotification(task_id="coordinator", status=TaskStatus.COMPLETED, summary=f"阶段完成: {phase.value}"))
        return results

    async def _run_parallel(self, items: List[WorkItem]) -> List[Any]:
        tasks = []
        for item in items:
            instance, execute_fn = self._prepare_worker(item)
            tasks.append(self._worker_mgr.run_agent(instance, execute_fn, item.context))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._collect_results(items, results)

    async def _run_serial_by_file(self, items: List[WorkItem]) -> List[Any]:
        file_groups: dict[str, List[WorkItem]] = {}
        ungrouped: List[WorkItem] = []
        for item in items:
            if item.target_files:
                key = "|".join(sorted(item.target_files))
                file_groups.setdefault(key, []).append(item)
            else:
                ungrouped.append(item)
        all_results: List[Any] = []
        group_coroutines = [self._run_serial_group(group_items) for group_items in file_groups.values()]
        if ungrouped:
            group_coroutines.append(self._run_parallel(ungrouped))
        group_results = await asyncio.gather(*group_coroutines, return_exceptions=True)
        for group_result in group_results:
            if isinstance(group_result, list):
                all_results.extend(group_result)
            elif isinstance(group_result, Exception):
                all_results.append({"error": str(group_result)})
            else:
                all_results.append(group_result)
        return all_results

    async def _run_serial_group(self, items: List[WorkItem]) -> List[Any]:
        results: List[Any] = []
        for item in items:
            if results:
                item.context["previous_results"] = list(results)
            instance, execute_fn = self._prepare_worker(item)
            try:
                results.append(await self._worker_mgr.run_agent(instance, execute_fn, item.context))
            except Exception as e:
                results.append({"error": str(e)})
        return results

    async def _run_region_parallel(self, items: List[WorkItem]) -> List[Any]:
        return await self._run_parallel(items)

    def _collect_results(self, items: List[WorkItem], raw_results: List[Any]) -> List[Any]:
        collected = []
        for item, result in zip(items, raw_results):
            if isinstance(result, Exception):
                collected.append({"item": item.description, "error": str(result)})
            else:
                collected.append(result)
        return collected