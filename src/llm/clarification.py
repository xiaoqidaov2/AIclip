from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ClarificationChoice:
    label: str
    description: str = ""


@dataclass(frozen=True)
class ClarificationQuestion:
    prompt: str
    choices: List[ClarificationChoice] = field(default_factory=list)
    free_text_label: str = "Other"


@dataclass(frozen=True)
class ClarificationBundle:
    reason: str
    questions: List[ClarificationQuestion] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def needs_input(self) -> bool:
        return bool(self.questions)

