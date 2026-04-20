from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from .llmConfig import LLMConfig
from .tools import ToolSetup


@dataclass(frozen=True)
class SkillDecision:
    skill_name: str
    locked: bool
    matched_terms: list[str]
    score: int
    reason: str = ""
    confidence: float = 0.0


class SkillRouter:
    def __init__(self, tool_setup: ToolSetup, llm_config: Optional[LLMConfig] = None, logger: Optional[Any] = None) -> None:
        self.tool_setup = tool_setup
        self.llm_config = llm_config
        self._logger = logger

    def resolve(
        self,
        text: str,
        locked_skill: Optional[str] = None,
        fallback_skill: Optional[str] = None,
    ) -> SkillDecision:
        if locked_skill:
            return SkillDecision(skill_name=locked_skill, locked=True, matched_terms=[], score=0, reason="locked by user", confidence=1.0)

        fallback = fallback_skill or self.tool_setup.get_skill().name
        if self.llm_config is not None:
            llm_match = self._llm_resolve(text, fallback=fallback)
            if llm_match is not None:
                return llm_match

        return SkillDecision(skill_name=fallback, locked=False, matched_terms=[], score=0, reason="default skill", confidence=0.0)

    def _llm_resolve(self, text: str, fallback: str) -> Optional[SkillDecision]:
        try:
            llm = self.llm_config.create_llm()
            skill_catalog = []
            for skill_name in self.tool_setup.get_skill_names():
                skill = self.tool_setup.get_skill(skill_name)
                skill_catalog.append(
                    {
                        "name": skill.name,
                        "title": skill.title,
                        "description": skill.description,
                        "tools": skill.tool_names,
                    }
                )

            prompt = (
                "Choose the best skill for the user request.\n"
                "Routing policy:\n"
                "- Use project_core for editing, subtitles, timing, render, validation, and general project work.\n"
                "- Use vision_inspection for image/video understanding, analysis, OCR, scene reading, or content inspection.\n"
                "- Use capcut_finalization only for explicit CapCut/剪映 draft packaging, stickers, effects, or other post-render finishing.\n"
                f"Available skills: {json.dumps(skill_catalog, ensure_ascii=False)}\n"
                f"Default skill: {fallback}\n"
                "Return JSON only with keys: skill_name, reason.\n"
                f"Request: {text}"
            )
            if self._logger:
                self._logger("route", "llm skill routing started")
            response: Any = llm.invoke([
                SystemMessage(content="You are a strict skill router."),
                HumanMessage(content=prompt),
            ])
            if self._logger:
                self._logger("route", "llm skill routing finished")
            content = getattr(response, "content", response)
            if not isinstance(content, str):
                return None
            payload = json.loads(content)
            skill_name = payload.get("skill_name")
            if skill_name not in self.tool_setup.get_skill_names():
                return None
            reason = str(payload.get("reason") or "llm routing")
            return SkillDecision(skill_name=skill_name, locked=False, matched_terms=[], score=0, reason=reason, confidence=0.6)
        except Exception:
            return None
