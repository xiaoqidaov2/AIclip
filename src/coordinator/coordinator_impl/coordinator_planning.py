from __future__ import annotations

from typing import Any, Dict, List

from .coordinator_models import WorkItem, WorkflowPhase, logger


class CoordinatorPlanningMixin:
    def _plan_research(self, user_request: str) -> List[WorkItem]:
        return [
            WorkItem(
                description=f"调查: {user_request}",
                phase=WorkflowPhase.RESEARCH,
                target_topics={user_request[:50]},
                context={
                    "prompt": (
                        f"请调查并分析以下需求：{user_request}\n\n"
                        "注意：当前环境为 Windows，如需执行命令请使用 Windows 命令（dir/type/python）"
                        "或 Python 脚本，禁止使用 Unix 专有命令（ls/head/grep/fc-list 等）。"
                    )
                },
            )
        ]

    def _plan_implementation(self, spec: Dict[str, Any]) -> List[WorkItem]:
        plan = spec.get("implementation_plan", [])
        if not plan:
            return [
                WorkItem(
                    description=f"实现: {spec.get('user_request', '')}",
                    phase=WorkflowPhase.IMPLEMENTATION,
                    context={"prompt": f"请按以下规范实现：{spec}"},
                )
            ]
        return [
            WorkItem(
                description=step.get("description", ""),
                phase=WorkflowPhase.IMPLEMENTATION,
                target_files=set(step.get("files", [])),
                context={"prompt": step.get("prompt", "")},
            )
            for step in plan
        ]

    def _plan_verification(self, spec: Dict[str, Any], impl_results: List[Any]) -> List[WorkItem]:
        verification_plan = spec.get("verification_plan", [])
        if not verification_plan:
            return [
                WorkItem(
                    description="验证实现结果",
                    phase=WorkflowPhase.VERIFICATION,
                    context={
                        "prompt": (
                            "请执行实际验证，不要只做口头总结。\n"
                            f"请验证以下实现结果：{impl_results}\n"
                            "要求：必须运行命令、观察输出、给出 PASS/FAIL 结论。"
                        ),
                        "spec": spec,
                    },
                )
            ]
        return [
            WorkItem(
                description=step.get("name", "验证步骤"),
                phase=WorkflowPhase.VERIFICATION,
                context={
                    "prompt": (
                        "你是严格的验证执行器。请只执行以下验证命令并报告结果，"
                        "不要总结性复述实现过程。\n"
                        f"验证名称：{step.get('name', '')}\n"
                        f"命令：{step.get('command', '')}\n"
                        f"期望输出：{step.get('expected_output', '')}\n"
                        "输出格式必须包含 Command run / Output observed / Result。"
                    ),
                    "spec": spec,
                    "verification_step": step,
                },
            )
            for step in verification_plan
        ]

    def _extract_research_summary(self, research_results: List[Any]) -> List[Any]:
        research_summary = []
        for result in research_results:
            if isinstance(result, dict):
                if "messages" in result:
                    for msg in result.get("messages", []):
                        if hasattr(msg, "content"):
                            research_summary.append(msg.content)
                elif "result" in result:
                    research_summary.append(result["result"])
            elif isinstance(result, str):
                research_summary.append(result)
        return research_summary

    def _fallback_spec(self, user_request: str, research_summary: List[Any]) -> Dict[str, Any]:
        logger.warning("LLM 综合失败，使用回退规范")
        return {
            "user_request": user_request,
            "research_summary": research_summary,
            "implementation_plan": [],
            "verification_plan": [],
        }