from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class ClarificationPolicy:
    confidence_threshold: float = 0.35
    max_questions: int = 5
    max_choices: int = 5
    free_text: bool = True


@dataclass(frozen=True)
class AgentRoleSpec:
    skill_name: str
    role_name: str
    system_prompt: str
    handoff_rules: List[str] = field(default_factory=list)
    clarification: ClarificationPolicy = field(default_factory=ClarificationPolicy)


@dataclass(frozen=True)
class AgentPolicy:
    default_role: str
    roles: Dict[str, AgentRoleSpec]

    def get_role(self, skill_name: str) -> AgentRoleSpec:
        fallback = AgentRoleSpec(
            skill_name=skill_name,
            role_name=self.default_role or "editor",
            system_prompt="Use tool outputs as the source of truth.",
        )
        return self.roles.get(skill_name) or self.roles.get(self.default_role) or next(iter(self.roles.values()), fallback)


def load_agent_policy(config_dir: Path) -> AgentPolicy:
    manifest_path = config_dir / "agent_roles.json"
    if not manifest_path.exists():
        return AgentPolicy(default_role="editor", roles={})
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AgentPolicy(default_role="editor", roles={})
    roles: Dict[str, AgentRoleSpec] = {}
    default_role = "editor"
    if isinstance(payload, dict):
        default_role = str(payload.get("default_role") or default_role)
        for raw in payload.get("roles", []):
            if not isinstance(raw, dict):
                continue
            skill_name = str(raw.get("skill_name") or "").strip()
            role_name = str(raw.get("role_name") or skill_name or default_role).strip()
            system_prompt = str(raw.get("system_prompt") or "").strip()
            if not skill_name or not role_name:
                continue
            clarification_raw = raw.get("clarification") if isinstance(raw.get("clarification"), dict) else {}
            clarification = ClarificationPolicy(
                confidence_threshold=float(clarification_raw.get("confidence_threshold", 0.35)),
                max_questions=max(1, min(5, int(clarification_raw.get("max_questions", 5)))),
                max_choices=max(1, min(5, int(clarification_raw.get("max_choices", 5)))),
                free_text=bool(clarification_raw.get("free_text", True)),
            )
            roles[skill_name] = AgentRoleSpec(
                skill_name=skill_name,
                role_name=role_name,
                system_prompt=system_prompt,
                handoff_rules=[str(item) for item in raw.get("handoff_rules", []) if str(item).strip()],
                clarification=clarification,
            )
    return AgentPolicy(default_role=default_role, roles=roles)
