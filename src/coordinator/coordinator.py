"""协调器模式 — 任务编排的核心。

角色：
- 协调器（Coordinator）：主 AI，负责任务分解、结果综合、与用户沟通
- Worker：子 Agent，执行具体的研究、实现、验证任务

工作流四阶段：
1. Research    — Workers 并行调查代码库、理解问题
2. Synthesis   — 协调器阅读结果、制定实现规范
3. Implementation — Workers 按规范修改代码
4. Verification — Workers 验证代码正常工作

并发策略：
- 只读任务（研究）：自由并行
- 写密集任务（实现）：按文件组串行
- 验证任务：可在不同文件区域与实现并行
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from langchain_core.messages import AIMessage, ToolMessage

from .task import TaskInstance, TaskStatus, TaskType


def _extract_result_text(result: Any, max_chars: int = 400) -> str:
    """从 agent 返回结果中提取可读文本摘要。"""
    if isinstance(result, dict):
        if "messages" in result:
            parts = []
            for msg in result["messages"]:
                c = getattr(msg, "content", "")
                if isinstance(c, str) and c.strip():
                    parts.append(c.strip())
            return " | ".join(parts)[:max_chars]
        if "content" in result:
            return str(result["content"])[:max_chars]
        if "error" in result:
            return f"[错误] {result['error']}"
    if isinstance(result, str):
        return result[:max_chars]
    return str(result)[:max_chars]
from .registry import TaskRegistry
from .notification import TaskNotification, NotificationQueue
from .worker import WorkerManager
from .context import ContextManager, ContextDecision
from .verification import VerificationAgent

logger = logging.getLogger(__name__)
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


class WorkflowPhase(str, Enum):
    RESEARCH = "research"
    SYNTHESIS = "synthesis"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"


class ConcurrencyMode(str, Enum):
    PARALLEL = "parallel"
    SERIAL_BY_FILE = "serial_by_file"
    REGION_PARALLEL = "region_parallel"


@dataclass
class WorkItem:
    """一个待编排的工作单元。"""
    description: str
    phase: WorkflowPhase
    target_files: Set[str] = field(default_factory=set)
    target_topics: Set[str] = field(default_factory=set)
    context: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    concurrency: ConcurrencyMode = ConcurrencyMode.PARALLEL


_PHASE_CONCURRENCY: Dict[WorkflowPhase, ConcurrencyMode] = {
    WorkflowPhase.RESEARCH: ConcurrencyMode.PARALLEL,
    WorkflowPhase.SYNTHESIS: ConcurrencyMode.SERIAL_BY_FILE,
    WorkflowPhase.IMPLEMENTATION: ConcurrencyMode.SERIAL_BY_FILE,
    WorkflowPhase.VERIFICATION: ConcurrencyMode.REGION_PARALLEL,
}


class CoordinatorMode:
    """协调器模式 — 四阶段工作流引擎。

    使用方式：
        coordinator = CoordinatorMode(agent, tools, registry)
        result = await coordinator.run(user_request)
    """

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
        self._phase_results: Dict[WorkflowPhase, List[Any]] = {p: [] for p in WorkflowPhase}

    async def run(self, user_request: str) -> Dict[str, Any]:
        """执行完整的四阶段工作流。"""
        logger.info("协调器启动: %s", user_request[:80])

        # 1. Research
        research_items = self._plan_research(user_request)
        research_results = await self._execute_phase(WorkflowPhase.RESEARCH, research_items)
        self._phase_results[WorkflowPhase.RESEARCH] = research_results

        # 2. Synthesis
        spec = await self._synthesize(user_request, research_results)
        self._phase_results[WorkflowPhase.SYNTHESIS] = [spec]

        # 3. Implementation
        impl_items = self._plan_implementation(spec)
        impl_results = await self._execute_phase(WorkflowPhase.IMPLEMENTATION, impl_items)
        self._phase_results[WorkflowPhase.IMPLEMENTATION] = impl_results

        # 4. Verification
        verify_items = self._plan_verification(spec, impl_results)
        verify_results = await self._execute_phase(WorkflowPhase.VERIFICATION, verify_items)
        self._phase_results[WorkflowPhase.VERIFICATION] = verify_results

        return self._summarize()

    async def run_phase(self, phase: WorkflowPhase, items: List[WorkItem]) -> List[Any]:
        """单独执行某个阶段。"""
        return await self._execute_phase(phase, items)

    async def _execute_phase(self, phase: WorkflowPhase, items: List[WorkItem]) -> List[Any]:
        """根据并发策略执行一个阶段的所有工作单元。"""
        self._current_phase = phase
        default_concurrency = _PHASE_CONCURRENCY[phase]
        logger.info("进入阶段: %s (%d 个工作单元)", phase.value, len(items))

        await self._notifications.enqueue(TaskNotification(
            task_id="coordinator",
            status=TaskStatus.RUNNING,
            summary=f"进入阶段: {phase.value}",
        ))

        if not items:
            await self._notifications.enqueue(TaskNotification(
                task_id="coordinator",
                status=TaskStatus.COMPLETED,
                summary=f"阶段完成: {phase.value}",
            ))
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

        await self._notifications.enqueue(TaskNotification(
            task_id="coordinator",
            status=TaskStatus.COMPLETED,
            summary=f"阶段完成: {phase.value}",
        ))
        return results

    async def _run_parallel(self, items: List[WorkItem]) -> List[Any]:
        """自由并行。"""
        tasks = []
        for item in items:
            instance, execute_fn = self._prepare_worker(item)
            tasks.append(self._worker_mgr.run_agent(instance, execute_fn, item.context))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._collect_results(items, results)

    async def _run_serial_by_file(self, items: List[WorkItem]) -> List[Any]:
        """按文件组串行。"""
        file_groups: Dict[str, List[WorkItem]] = {}
        ungrouped: List[WorkItem] = []

        for item in items:
            if item.target_files:
                key = "|".join(sorted(item.target_files))
                file_groups.setdefault(key, []).append(item)
            else:
                ungrouped.append(item)

        all_results: List[Any] = []
        group_coroutines = []
        for file_key, group_items in file_groups.items():
            group_coroutines.append(self._run_serial_group(group_items))

        if ungrouped:
            group_coroutines.append(self._run_parallel(ungrouped))

        group_results = await asyncio.gather(*group_coroutines, return_exceptions=True)
        for gr in group_results:
            if isinstance(gr, list):
                all_results.extend(gr)
            elif isinstance(gr, Exception):
                all_results.append({"error": str(gr)})
            else:
                all_results.append(gr)

        return all_results

    async def _run_serial_group(self, items: List[WorkItem]) -> List[Any]:
        """组内串行执行，前序结果自动传递给后续步骤。"""
        results = []
        for item in items:
            if results:
                item.context["previous_results"] = list(results)
            instance, execute_fn = self._prepare_worker(item)
            try:
                result = await self._worker_mgr.run_agent(instance, execute_fn, item.context)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e)})
        return results

    async def _run_region_parallel(self, items: List[WorkItem]) -> List[Any]:
        """区域并行。"""
        return await self._run_parallel(items)

    def _prepare_worker(self, item: WorkItem) -> tuple[TaskInstance, Callable]:
        """为 WorkItem 准备 Worker。"""
        decision, existing_id = self._context_mgr.decide(item.target_files, item.target_topics)

        if decision == ContextDecision.CONTINUE and existing_id:
            instance = self._worker_mgr.get_agent(existing_id)
            if instance is not None and not instance.is_terminal:
                logger.info("续用 Worker %s", existing_id)
                ctx = self._context_mgr.get_context(existing_id)
                if ctx:
                    ctx.message_count += 1
            else:
                # Worker 已处于终态（completed/failed/killed），不可续用
                logger.info("Worker %s 已终止，标记过期并新建", existing_id)
                self._context_mgr.mark_stale(existing_id)
                instance = self._create_worker(item)
        else:
            logger.info("新建 Worker")
            instance = self._create_worker(item)

        execute_fn = self._make_execute_fn(item)
        return instance, execute_fn

    def _create_worker(self, item: WorkItem) -> TaskInstance:
        """注册并创建新 Worker 实例。"""
        instance = self._worker_mgr.register_async_agent(
            name=f"worker-{item.phase.value}-{item.description[:20]}",
            task_type=TaskType.LOCAL_AGENT,
            metadata={"phase": item.phase.value, "description": item.description},
        )
        self._context_mgr.register_worker(instance.id)
        self._context_mgr.update_worker(
            instance.id,
            files=item.target_files,
            topics=item.target_topics,
        )
        return instance

    def _make_execute_fn(self, item: WorkItem) -> Callable:
        """构建 Worker 的执行函数。"""
        agent = self._agent

        async def execute(instance: TaskInstance, context: Dict[str, Any]) -> Any:
            verification_step = context.get("verification_step")
            if verification_step:
                verification_context = {
                    "checks": [
                        {
                            "name": verification_step.get("name", item.description),
                            "description": verification_step.get("description", item.description),
                            "command": verification_step.get("command", ""),
                            "expected_output": verification_step.get("expected_output"),
                        }
                    ]
                }
                report = await self._verification_agent.verify(verification_context)
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
                for i, r in enumerate(prev_results):
                    text = _extract_result_text(r)
                    if text:
                        summaries.append(f"步骤{i + 1}输出: {text}")
                if summaries:
                    prompt = (
                        prompt
                        + "\n\n【前序步骤已完成，结果如下，请依据实际路径继续执行】\n"
                        + "\n".join(summaries)
                    )
            return await self._run_agent_with_visibility(
                agent=agent,
                messages=[{"role": "user", "content": prompt}],
                label=f"worker:{instance.name}",
            )

        return execute

    def _plan_research(self, user_request: str) -> List[WorkItem]:
        """根据用户请求规划研究工作单元。"""
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

    async def _synthesize(self, user_request: str, research_results: List[Any]) -> Dict[str, Any]:
        """协调器综合研究结果，制定实现规范。

        关键：协调器必须理解研究结果，综合成具体规范，而不是懒惰地说"基于你的发现"。
        """
        self._current_phase = WorkflowPhase.SYNTHESIS
        logger.info("综合阶段: 处理 %d 条研究结果", len(research_results))

        # 提取研究结果中的关键信息
        research_summary = []
        for result in research_results:
            if isinstance(result, dict):
                if "messages" in result:
                    messages = result.get("messages", [])
                    for msg in messages:
                        if hasattr(msg, "content"):
                            research_summary.append(msg.content)
                elif "result" in result:
                    research_summary.append(result["result"])
            elif isinstance(result, str):
                research_summary.append(result)

        # 调用 LLM 综合研究结果
        synthesis_prompt = f"""你是一个协调器，需要综合研究结果并制定具体的实现规范。

用户请求: {user_request}

研究结果:
{chr(10).join(f"- {r[:500]}" for r in research_summary[:5])}

请输出 JSON 格式的实现规范，包含：
1. implementation_plan: 实现步骤列表，每个步骤包含 description, files, prompt
2. verification_plan: 验证步骤列表，每个步骤包含 name, command, expected_output

注意：
- 必须具体明确，不能说"基于你的发现"
- 每个步骤必须有可执行的命令或操作
- 验证步骤必须实际运行，不能只读代码
- 当前运行环境为 Windows，禁止在 prompt 中使用 Unix 命令（head/tail/ls/grep/fc-list/find /usr 等）
- 如需创建或覆盖文本文件，优先使用 write_file；如需列举文件或检查目录，使用 list_directory、Python 代码（通过 bash_command 工具）或 Windows 命令（dir、type）
- 每个步骤的 prompt 必须明确写出：输入文件的完整路径、预期生成的输出文件完整路径（无首尾空格）
- 步骤间有依赖时，后续步骤的 prompt 必须说明"前序步骤将提供实际路径，请以实际收到的路径为准"
- 文件路径不得包含前后多余的空格或换行符
"""

        try:
            response = await self._run_agent_with_visibility(
                agent=self._agent,
                messages=[{"role": "user", "content": synthesis_prompt}],
                label="coordinator:synthesis",
            )

            if response:
                content = ""
                if isinstance(response, dict):
                    if "messages" in response:
                        for msg in response["messages"]:
                            if hasattr(msg, "content"):
                                content = msg.content
                                break
                    elif "content" in response:
                        content = response["content"]
                elif hasattr(response, "content"):
                    content = response.content

                try:
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()
                    elif "```" in content:
                        json_start = content.find("```") + 3
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()

                    spec = json.loads(content)
                    spec["user_request"] = user_request
                    spec["research_summary"] = research_summary
                    return spec
                except (json.JSONDecodeError, ValueError):
                    pass

        except Exception as e:
            logger.warning("LLM 综合失败: %s", e)

        return {
            "user_request": user_request,
            "research_summary": research_summary,
            "implementation_plan": [],
            "verification_plan": [],
        }

    async def _run_agent_with_visibility(
        self,
        agent: Any,
        messages: List[Dict[str, Any]],
        label: str,
    ) -> Any:
        """Run a LangChain agent with live tool-call and assistant-content visibility."""
        if hasattr(agent, "stream"):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self._drain_stream_sync,
                agent,
                messages,
                label,
            )

        if hasattr(agent, "ainvoke"):
            return await agent.ainvoke({"messages": messages})

        if hasattr(agent, "invoke"):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, agent.invoke, {"messages": messages})

        return {"result": f"执行: {messages[-1].get('content', '')}"}

    def _drain_stream_sync(self, agent: Any, messages: List[Dict[str, Any]], label: str) -> Any:
        """Synchronously consume agent.stream so intermediate events are printed live."""
        final_content = ""
        collected_messages: List[Any] = []
        seen_tool_calls: Set[str] = set()

        try:
            for chunk in agent.stream({"messages": messages}):
                if not isinstance(chunk, dict):
                    continue

                chunk_messages: List[Any] = []
                if "model" in chunk:
                    chunk_messages = chunk["model"].get("messages", [])
                elif "tools" in chunk:
                    chunk_messages = chunk["tools"].get("messages", [])
                elif "agent" in chunk:
                    chunk_messages = chunk["agent"].get("messages", [])
                elif "messages" in chunk:
                    chunk_messages = chunk["messages"]

                for msg in chunk_messages:
                    collected_messages.append(msg)
                    msg_type = type(msg).__name__
                    if msg_type == "ToolMessage" or (hasattr(msg, "name") and not getattr(msg, "tool_calls", None)):
                        self._print_tool_result(msg, label)
                    elif msg_type in {"AIMessage", "AIMessageChunk"} or hasattr(msg, "tool_calls") or hasattr(msg, "content"):
                        final_content = self._print_ai_message(msg, seen_tool_calls, final_content, label)
        except Exception as e:
            print(f"\n└─ [{label}] 流式执行失败: {e}", flush=True)

        return {"messages": collected_messages, "content": final_content}

    def _print_ai_message(
        self,
        msg: Any,
        seen_tool_calls: Set[str],
        current_content: str,
        label: str,
    ) -> str:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tool_call in tool_calls:
                tool_call_id = tool_call.get("id", "")
                if tool_call_id and tool_call_id in seen_tool_calls:
                    continue
                if tool_call_id:
                    seen_tool_calls.add(tool_call_id)
                name = tool_call.get("name", "unknown")
                args = tool_call.get("args", {})
                print(f"\n┌─ [{label}] 调用工具: {name}", flush=True)
                if args:
                    print(f"│  参数: {self._format_args(args)}", flush=True)

        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.strip() and content != current_content:
            current_content = content
            print(f"\n└─ [{label}] AI: {self._truncate_text(content, 500)}", flush=True)

        return current_content

    def _print_tool_result(self, msg: Any, label: str) -> None:
        name = getattr(msg, "name", "tool")
        content = getattr(msg, "content", "")
        print(f"\n└─ [{label}] 工具结果: [{name}] {self._truncate_text(str(content), 500)}", flush=True)

    def _format_args(self, args: Dict[str, Any]) -> str:
        if not args:
            return ""
        parts = []
        for key, value in args.items():
            value_text = str(value)
            if len(value_text) > 60:
                value_text = value_text[:57] + "..."
            parts.append(f"{key}={value_text}")
        return "(" + ", ".join(parts) + ")"

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _plan_implementation(self, spec: Dict[str, Any]) -> List[WorkItem]:
        """根据规范规划实现工作单元。"""
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
        """根据规范和实现结果规划验证工作单元。"""
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

    def _collect_results(self, items: List[WorkItem], raw_results: List) -> List[Any]:
        """从 gather 结果中收集，处理异常。"""
        collected = []
        for item, result in zip(items, raw_results):
            if isinstance(result, Exception):
                collected.append({
                    "item": item.description,
                    "error": str(result),
                })
            else:
                collected.append(result)
        return collected

    def _summarize(self) -> Dict[str, Any]:
        """汇总四阶段结果。"""
        return {
            "phases": {
                phase.value: results
                for phase, results in self._phase_results.items()
            },
            "notifications": [n.to_xml() for n in self._notifications.history],
            "workers": [
                {
                    "id": w.id,
                    "name": w.name,
                    "status": w.status.value,
                    "elapsed": w.elapsed,
                }
                for w in self._worker_mgr.get_all_agents()
            ],
        }

    async def process_notifications(self) -> List[TaskNotification]:
        """处理所有待处理通知。"""
        return await self._notifications.drain()

    @property
    def current_phase(self) -> WorkflowPhase:
        return self._current_phase

    @property
    def worker_manager(self) -> WorkerManager:
        return self._worker_mgr

    @property
    def context_manager(self) -> ContextManager:
        return self._context_mgr

    @property
    def notification_queue(self) -> NotificationQueue:
        return self._notifications
