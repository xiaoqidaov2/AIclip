from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    source: str
    attr: str
    doc_file: str
    register: bool = True


@dataclass(frozen=True)
class SkillSpec:
    name: str
    title: str
    description: str
    tool_names: List[str]
    doc_names: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    doc_file: Optional[str] = None


@dataclass(frozen=True)
class ResourceSpec:
    module: str
    class_name: str


@dataclass(frozen=True)
class SkillMatch:
    name: str
    score: int
    matched_terms: List[str]
