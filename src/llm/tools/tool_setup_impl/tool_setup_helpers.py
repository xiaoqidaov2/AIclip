import importlib
import json
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

from src.editor_core.contracts import serialize_tool_result
from .tool_setup_models import ResourceSpec, SkillSpec, ToolSpec


def build_resource_specs() -> Dict[str, ResourceSpec]:
    return {
        "project": ResourceSpec("src.llm.tools.project_tool", "ProjectTool"),
        "net_asset": ResourceSpec("src.llm.tools.net_asset_tool", "NetAssetTool"),
        "vision": ResourceSpec("src.llm.tools.vision_tool", "VisionTool"),
    }


def load_doc(docs_dir: Path, doc_file: str) -> str:
    doc_path = docs_dir / doc_file
    return doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""


def load_skill_doc(skills_dir: Path, skills: Dict[str, SkillSpec], skill_name: str) -> str:
    skill = skills.get(skill_name)
    candidates = [skills_dir / skill.doc_file] if skill and skill.doc_file else []
    candidates.append(skills_dir / f"{skill_name}.md")
    for path in candidates:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8").strip()
            except OSError:
                return ""
    return ""


def load_skill_overrides(skills_dir: Path, skills: Dict[str, SkillSpec], default_skill_name: str) -> tuple[dict[str, SkillSpec], str]:
    manifest_path = skills_dir / "skills.json"
    if not manifest_path.exists():
        return skills, default_skill_name
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return skills, default_skill_name
    next_default = payload.get("default_skill") if isinstance(payload, dict) else None
    if not isinstance(next_default, str) or not next_default:
        next_default = default_skill_name
    for item in payload.get("skills", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        tool_names = item.get("tool_names")
        if not isinstance(name, str) or not isinstance(tool_names, list):
            continue
        existing = skills.get(name)
        skills[name] = SkillSpec(name=name, title=item.get("title", existing.title if existing else name), description=item.get("description", existing.description if existing else ""), tool_names=[str(tool) for tool in tool_names], doc_names=[str(doc) for doc in item.get("doc_names", existing.doc_names if existing else [])], keywords=[str(keyword) for keyword in item.get("keywords", existing.keywords if existing else [])], doc_file=item.get("doc_file") if isinstance(item.get("doc_file"), str) else (existing.doc_file if existing else None))
    return skills, next_default


def get_resource(resource_instances: Dict[str, Any], resource_specs: Dict[str, ResourceSpec], source: str) -> Any:
    if source in resource_instances:
        return resource_instances[source]
    spec = resource_specs[source]
    module = importlib.import_module(spec.module)
    resource = getattr(module, spec.class_name)()
    resource_instances[source] = resource
    return resource


def wrap_callable(tool_name: str, description: str, raw_callable: Any):
    @wraps(raw_callable)
    def adapter(*args, **kwargs):
        return serialize_tool_result(tool_name, raw_callable(*args, **kwargs))
    adapter.__doc__ = description
    adapter.__name__ = tool_name
    return adapter


def build_system_prompt(
    base_prompt: str,
    skill: SkillSpec,
    docs: str,
    skill_guide: str,
    role_name: str = "editor",
    handoff_rules: List[str] | None = None,
) -> str:
    rules = handoff_rules or []
    prompt = (
        base_prompt.rstrip()
        + "\n\n## Active Role\n"
        + role_name
        + "\n\n## Tool Documentation\n"
        + docs
        + "\n\n## Active Skill\n"
        + f"{skill.title} ({skill.name})\n"
        + skill.description
    )
    if skill_guide:
        prompt += f"\n\n## Skill Guide\n{skill_guide}"
    if rules:
        prompt += "\n\n## Handoff Rules\n" + "\n".join(f"- {rule}" for rule in rules)
    prompt += (
        "\n\n## Allowed Tools\n"
        + ", ".join(skill.tool_names)
        + "\n\n## Tool Result Contract\n"
        + "Use `decision`, `render_state`, `validation`, `state`, `payload`, and `next_actions` first.\n"
        + "Treat `message` and `summary` as display text only.\n"
        + "Treat `next_actions` as structured information, not as an instruction to auto-execute.\n"
        + "Default to direct execution when the request is sufficiently clear.\n"
        + "Only switch into planning or clarification when ambiguity is material.\n"
        + "For list/dict tool args (such as `spans`, `parameters`), pass native JSON values, not quoted JSON strings.\n"
        + "If you need to style, reposition, or add effects to 3 or more subtitles, prefer `batch_update_project_subtitles` instead of many small subtitle tool calls.\n"
        + "If the request targets only a few words in one subtitle, use subtitle span tools instead of replacing the whole cue.\n"
        + "Do not ask the user to guess subtitle content.\n"
        + "Only call tools that belong to the active skill."
    )
    return prompt
