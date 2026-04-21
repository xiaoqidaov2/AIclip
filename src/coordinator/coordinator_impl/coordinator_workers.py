from __future__ import annotations

from typing import Any, Callable, Dict

from ..context import ContextDecision
from .coordinator_models import WorkItem, _extract_result_text, logger
from ..task import TaskInstance, TaskType


class CoordinatorWorkersMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _prepare_worker(self, item: WorkItem) -> tuple[TaskInstance, Callable[..., Any]]:
        decision, existing_id = self._context_mgr.decide(item.target_files, item.target_topics)
        if decision == ContextDecision.CONTINUE and existing_id:
            instance = self._worker_mgr.get_agent(existing_id)
            if instance is not None and not instance.is_terminal:
                logger.info("续用 Worker %s", existing_id)
                ctx = self._context_mgr.get_context(existing_id)
                if ctx:
                    ctx.message_count += 1
            else:
                logger.info("Worker %s 已终止，标记过期并新建", existing_id)
                self._context_mgr.mark_stale(existing_id)
                instance = self._create_worker(item)
        else:
            logger.info("新建 Worker")
            instance = self._create_worker(item)
        return instance, self._make_execute_fn(item)

    def _create_worker(self, item: WorkItem) -> TaskInstance:
        instance = self._worker_mgr.register_async_agent(
            name=f"worker-{item.phase.value}-{item.description[:20]}",
            task_type=TaskType.LOCAL_AGENT,
            metadata={"phase": item.phase.value, "description": item.description},
        )
        self._context_mgr.register_worker(instance.id)
        self._context_mgr.update_worker(instance.id, files=item.target_files, topics=item.target_topics)
        return instance

    def _make_execute_fn(self, item: WorkItem) -> Callable[..., Any]:
        agent = self._agent

        async def execute(instance: TaskInstance, context: Dict[str, Any]) -> Any:
            verification_step = context.get("verification_step")
            if verification_step:
                report = await self._verification_agent.verify(
                    {
                        "checks": [
                            {
                                "name": verification_step.get("name", item.description),
                                "description": verification_step.get("description", item.description),
                                "command": verification_step.get("command", ""),
                                "expected_output": verification_step.get("expected_output"),
                            }
                        ]
                    }
                )
                first_check = report.checks[0] if report.checks else None
                return {
                    "verification_report": {
                        "all_passed": report.all_passed,
                        "summary": report.summary,
                        "checks": [
                            {
                                "name": check.name,
                                "description": check.description,
                                "command_run": check.command_run,
                                "output_observed": check.output_observed,
                                "result": check.result.value,
                                "error_message": check.error_message,
                            }
                            for check in report.checks
                        ],
                    },
                    "command_run": first_check.command_run if first_check else "",
                    "output_observed": first_check.output_observed if first_check else "",
                    "result": first_check.result.value if first_check else "SKIP",
                }
            prompt = context.get("prompt", item.description)
            prev_results = context.get("previous_results", [])
            if prev_results:
                summaries = []
                for index, result in enumerate(prev_results):
                    text = _extract_result_text(result)
                    if text:
                        summaries.append(f"步骤{index + 1}输出: {text}")
                if summaries:
                    prior_block = "\n".join(summaries)
                    prompt = (
                        prompt
                        + "\n\n【前序步骤已完成，结果如下，请依据实际路径继续执行】\n"
                        + "<prior_step_output>\n"
                        + prior_block
                        + "\n</prior_step_output>"
                    )
            return await self._run_agent_with_visibility(agent=agent, messages=[{"role": "user", "content": prompt}], label=f"worker:{instance.name}")

        return execute