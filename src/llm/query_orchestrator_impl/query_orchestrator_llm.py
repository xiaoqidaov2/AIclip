from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ..skill_router import SkillDecision

_json_fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _strip_json_fence(text: str) -> str:
    m = _json_fence_re.search(text)
    return m.group(1) if m else text.strip()


_logger = logging.getLogger(__name__)


def llm_plan(user_input: str, route: SkillDecision, tool_setup: Any, llm_config: Optional[Any], logger: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    if llm_config is None:
        return None
    try:
        llm = llm_config.create_llm()
        skill_catalog = []
        for skill_name in tool_setup.get_skill_names():
            skill = tool_setup.get_skill(skill_name)
            skill_catalog.append(
                {
                    "name": skill.name,
                    "title": skill.title,
                    "description": skill.description,
                    "tools": skill.tool_names,
                    "keywords": getattr(skill, "keywords", []),
                }
            )
        prompt = (
            "Create a structured multi-stage execution plan for the request.\n"
            "Return JSON only with keys: primary_skill, skills, steps, nudges, clarification.\n"
            "Each step must have: phase, skill_name, reason, prompt, input_focus, allowed_tools, stop_conditions.\n"
            "Valid phases: discovery, plan, execute, compress, nudge.\n"
            "Add clarification only if required before editing.\n"
            "Clarification shape: {reason, questions:[{prompt, choices:[{label, description}], free_text_label}]}.\n"
            "Limit clarification to at most 5 questions and 5 choices per question.\n"
            "Use only the available skill names.\n"
            f"Planner skill: {tool_setup.get_planner_skill_name()}\n"
            f"Route suggestion: {route.skill_name}\n"
            f"Request: {user_input}\n"
            f"Available skills: {json.dumps(skill_catalog, ensure_ascii=False)}"
        )
        if logger:
            logger("plan", "llm planner started")
        response: Any = llm.invoke([SystemMessage(content="You are a strict query planner and skill orchestrator."), HumanMessage(content=prompt)])
        if logger:
            logger("plan", "llm planner finished")
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            return None
        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError:
            _logger.warning("llm_plan: failed to parse LLM JSON response; raw: %.200s", content)
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("steps"), list):
            return None
        return payload
    except Exception:
        return None
