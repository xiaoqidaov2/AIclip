from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.llm.query_orchestrator import QueryOrchestrator
from src.llm.skill_router import SkillDecision


@dataclass
class FakeSkill:
    name: str
    title: str
    description: str = ""
    tool_names: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


class FakeToolSetup:
    def __init__(self) -> None:
        self._skills = {
            "project_core": FakeSkill(
                name="project_core",
                title="Project Core",
                tool_names=["load_project", "prepare_project_render", "render_project"],
            ),
            "vision_inspection": FakeSkill(
                name="vision_inspection",
                title="Vision Inspection",
                tool_names=["vision_analyze_media"],
            ),
        }

    def get_skill(self, name: str | None = None) -> FakeSkill:
        return self._skills[name or "project_core"]

    def get_skill_names(self) -> list[str]:
        return list(self._skills)


class FakeSkillRouter:
    def resolve(self, text: str, locked_skill: str | None = None, fallback_skill: str | None = None) -> SkillDecision:
        return SkillDecision(
            skill_name=locked_skill or "project_core",
            locked=bool(locked_skill),
            matched_terms=[],
            score=0,
            reason="fake route",
            confidence=0.6,
        )


def test_plan_keeps_single_routed_skill_even_with_session_context() -> None:
    orchestrator = QueryOrchestrator(FakeSkillRouter(), FakeToolSetup())

    result = orchestrator.plan(
        "render feedback",
        session_context={
            "project_path": "C:/projects/demo/project.json",
            "final_path": "C:/tmp/demo_final.mp4",
            "last_operation": "render_project",
            "short_video_score": 78.7,
        },
    )

    assert result.planner_mode == "heuristic"
    assert [step.skill_name for step in result.steps] == ["project_core"]


def test_plan_keeps_routed_skill_for_normal_requests() -> None:
    orchestrator = QueryOrchestrator(FakeSkillRouter(), FakeToolSetup())

    result = orchestrator.plan(
        "智能剪辑",
        session_context={
            "project_path": "C:/projects/demo/project.json",
            "final_path": "C:/tmp/demo_final.mp4",
        },
    )

    assert [step.skill_name for step in result.steps] == ["project_core"]
