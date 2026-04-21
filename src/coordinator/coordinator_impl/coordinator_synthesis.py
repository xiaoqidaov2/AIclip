from __future__ import annotations

import json
from typing import Any, Dict, List

from .coordinator_models import WorkflowPhase, logger


class CoordinatorSynthesisMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    async def _synthesize(self, user_request: str, research_results: List[Any]) -> Dict[str, Any]:
        self._current_phase = WorkflowPhase.SYNTHESIS
        logger.info("综合阶段: 处理 %d 条研究结果", len(research_results))
        research_summary = self._extract_research_summary(research_results)
        synthesis_prompt = self._build_synthesis_prompt(user_request, research_summary)
        try:
            response = await self._run_agent_with_visibility(
                agent=self._agent,
                messages=[{"role": "user", "content": synthesis_prompt}],
                label="coordinator:synthesis",
            )
            content = self._response_content(response)
            spec = self._parse_synthesis_content(content)
            if spec is not None:
                spec["user_request"] = user_request
                spec["research_summary"] = research_summary
                return spec
        except Exception as e:
            logger.warning("LLM 综合失败: %s", e)
        return self._fallback_spec(user_request, research_summary)

    def _build_synthesis_prompt(self, user_request: str, research_summary: List[Any]) -> str:
        return f"""你是一个协调器，需要综合研究结果并制定具体的实现规范。

用户请求: {user_request}

研究结果:

{chr(10).join(f'- {r[:500]}' for r in research_summary[:5])}

请输出 JSON 格式的实现规范，包含：
1. implementation_plan: 实现步骤列表，每个步骤包含 description, files, prompt
2. verification_plan: 验证步骤列表，每个步骤包含 name, command, expected_output

注意：
- 必须具体明确，不能说"基于你的发现"
- 每个步骤必须有可执行的命令或操作
- 验证步骤必须实际运行，不能只读代码
- 当前运行环境为 Windows，禁止在 prompt 中使用 Unix 命令（head/tail/ls/grep/fc-list/find /usr 等）
- 如需修改项目结构或渲染流程，优先使用 project 工具。避免直接使用 shell 或临时媒体处理路径。
- 每个步骤的 prompt 必须明确写出：输入文件的完整路径、预期生成的输出文件完整路径（无首尾空格）
- 步骤间有依赖时，后续步骤的 prompt 必须说明"前序步骤将提供实际路径，请以实际收到的路径为准"
- 文件路径不得包含前后多余的空格或换行符
"""

    def _response_content(self, response: Any) -> str:
        if isinstance(response, dict):
            if "messages" in response:
                for msg in response["messages"]:
                    if hasattr(msg, "content"):
                        return msg.content
            if "content" in response:
                return response["content"]
        return response.content if hasattr(response, "content") else ""

    def _parse_synthesis_content(self, content: str) -> Dict[str, Any] | None:
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return None