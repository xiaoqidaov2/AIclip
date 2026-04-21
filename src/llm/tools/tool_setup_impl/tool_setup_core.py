from pathlib import Path
from typing import Any, Dict, List, Optional

from ..tool_registration import ToolRegistration
from .tool_setup_catalog_skills import build_skill_specs
from .tool_setup_catalog_tools import build_tool_specs
from .tool_setup_helpers import build_resource_specs, build_system_prompt as compose_system_prompt, get_resource, load_doc, load_skill_doc, load_skill_overrides, wrap_callable
from .tool_setup_models import SkillMatch, SkillSpec, ToolSpec


class ToolSetup:
    """Central tool registry, documentation, and ordered tool access."""

    def __init__(self) -> None:
        self.registry = ToolRegistration()
        self._docs_dir = Path(__file__).resolve().parents[3] / "resources" / "docs"
        self._skills_dir = Path(__file__).resolve().parents[3] / "resources" / "skills"
        self._resource_specs = build_resource_specs()
        self._resource_instances: Dict[str, Any] = {}
        self._tool_cache: Dict[str, Any] = {}
        self._specs: List[ToolSpec] = build_tool_specs()
        self._skills: Dict[str, SkillSpec] = build_skill_specs(self._specs)
        self._default_skill_name = "project_core"
        self._planner_skill_name = "workflow_orchestrator"
        self._skills, self._default_skill_name = load_skill_overrides(self._skills_dir, self._skills, self._default_skill_name)
        for spec in self._specs:
            self.registry.register_tool_doc(spec.name, load_doc(self._docs_dir, spec.doc_file))

    @property
    def registered_names(self) -> List[str]:
        return [spec.name for spec in self._specs if spec.register]

    def get_skill_names(self) -> List[str]:
        return list(self._skills.keys())

    def suggest_skill(self, text: str, fallback: Optional[str] = None) -> SkillMatch:
        candidate_text = (text or "").lower()
        best_name = fallback or self._default_skill_name
        best_score = 0
        best_terms: List[str] = []
        for skill in self._skills.values():
            matched_terms = [keyword for keyword in skill.keywords if keyword and keyword.lower() in candidate_text]
            score = len(matched_terms)
            if score > best_score:
                best_name = skill.name
                best_score = score
                best_terms = matched_terms
        return SkillMatch(name=best_name, score=best_score, matched_terms=best_terms)

    def get_skill(self, name: Optional[str] = None) -> SkillSpec:
        skill_name = name or self._default_skill_name
        if skill_name not in self._skills:
            raise KeyError(f"Unknown skill: {skill_name}. Available skills: {', '.join(self.get_skill_names())}")
        return self._skills[skill_name]

    def get_planner_skill_name(self) -> str:
        return self._planner_skill_name if self._planner_skill_name in self._skills else self._default_skill_name

    def _resolve_callable(self, spec: ToolSpec):
        resource = get_resource(self._resource_instances, self._resource_specs, spec.source)
        raw_callable = resource[spec.attr] if isinstance(resource, dict) else getattr(resource, spec.attr)
        return wrap_callable(spec.name, spec.description, raw_callable)

    def get_tool(self, name: str):
        if name in self._tool_cache:
            return self._tool_cache[name]
        spec = next((item for item in self._specs if item.name == name and item.register), None)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        tool = self._resolve_callable(spec)
        self.registry.register_tool(spec.name, tool)
        self._tool_cache[name] = tool
        return tool

    def get_tools(self, names: Optional[List[str]] = None):
        return [self.get_tool(name) for name in (names or self.registered_names)]

    def get_skill_tools(self, name: Optional[str] = None):
        return self.get_tools(self.get_skill(name).tool_names)

    def get_documentation(self, names: Optional[List[str]] = None) -> str:
        requested = set(names) if names else None
        docs = []
        for spec in self._specs:
            if requested is not None and spec.name not in requested:
                continue
            header = f"{spec.title} ({spec.name})" if spec.register else f"{spec.title} [doc-only]"
            docs.extend([f"=== {header} ===", self.registry.get_tool_doc(spec.name) or spec.description, ""])
        return "\n".join(docs)

    def build_system_prompt(self, base_prompt: str, skill_name: Optional[str] = None) -> str:
        skill = self.get_skill(skill_name)
        doc_names = list(dict.fromkeys(skill.doc_names + skill.tool_names))
        return compose_system_prompt(base_prompt, skill, self.get_documentation(doc_names), load_skill_doc(self._skills_dir, self._skills, skill.name))
