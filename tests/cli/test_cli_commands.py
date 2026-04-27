from dataclasses import dataclass, field
from pathlib import Path
from types import MethodType
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main as main_module
from src.cli.app import CLIApp
from src.llm.query_orchestrator import OrchestrationPhase, PlannedStep


@dataclass
class FakeSkill:
    name: str
    title: str
    description: str = ""
    tool_names: list[str] = field(default_factory=list)


class FakeToolSetup:
    def __init__(self) -> None:
        self._skills = {
            "project_core": FakeSkill(
                name="project_core",
                title="Project Core",
                description="default skill",
                tool_names=[
                    "get_project_summary",
                    "prepare_project_render",
                    "render_project",
                ],
            ),
            "vision_inspection": FakeSkill(
                name="vision_inspection",
                title="Vision Inspection",
                description="vision skill",
                tool_names=["vision_analyze_media"],
            ),
        }

    def get_skill(self, name: str | None = None) -> FakeSkill:
        return self._skills[name or "project_core"]

    def get_skill_names(self) -> list[str]:
        return list(self._skills)

    def get_skill_tools(self, skill_name: str | None = None) -> list[object]:
        return []


class FakeLLMConfig:
    def create_llm(self) -> object:
        raise AssertionError("LLM should not be created for builtin command tests")


class FakeCLIAppForMain:
    instances: list["FakeCLIAppForMain"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.commands: list[str] = []
        self.run_calls = 0
        type(self).instances.append(self)

    def run_once(self, command: str) -> None:
        self.commands.append(command)

    def run(self) -> None:
        self.run_calls += 1


def build_app(agent_calls: list[str]) -> CLIApp:
    tool_setup = FakeToolSetup()

    def agent_factory(skill_name: str | None) -> object:
        agent_calls.append(skill_name or "")
        return object()

    return CLIApp(
        agent_factory=agent_factory,
        tool_setup=tool_setup,
        llm_config=FakeLLMConfig(),
    )


def test_help_does_not_initialize_runtime(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/help")

    captured = capsys.readouterr().out
    assert "/plan <request>" in captured
    assert "[skill] loading" not in captured
    assert agent_calls == []


def test_skills_does_not_initialize_runtime(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/skills")

    captured = capsys.readouterr().out
    assert "project_core" in captured
    assert "full" not in captured
    assert "workflow_orchestrator" not in captured
    assert "[skill] loading" not in captured
    assert agent_calls == []


def test_plan_requires_request_text(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/plan")

    captured = capsys.readouterr().out
    assert "Usage: /plan <request>" in captured
    assert agent_calls == []


def test_status_shows_pending_plan_flag(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/status")

    captured = capsys.readouterr().out
    assert "Active skill: project_core" in captured
    assert "Routing mode: auto" in captured
    assert "Planner mode: heuristic" in captured
    assert "Pending plan: no" in captured


def test_clear_resets_pending_plan(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)
    app._pending_orchestration = object()
    app._pending_input = "plan me"

    app.run_once("/clear")
    cleared = capsys.readouterr().out

    app.run_once("/status")
    status = capsys.readouterr().out

    assert "Conversation history cleared." in cleared
    assert "Pending plan: no" in status


def test_main_reuses_cli_app_across_multiple_run_calls(monkeypatch) -> None:
    FakeCLIAppForMain.instances.clear()
    monkeypatch.setattr(main_module, "CLIApp", FakeCLIAppForMain)

    app = main_module.Main()
    app.run(command="/plan hello")
    app.run(command="/status")

    assert len(FakeCLIAppForMain.instances) == 1
    assert FakeCLIAppForMain.instances[0].commands == ["/plan hello", "/status"]


def test_normal_input_executes_immediately(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    def fake_plan(user_input, locked_skill=None, session_context=None):
        class Result:
            def __init__(self) -> None:
                self.route = type(
                    "Route",
                    (),
                    {
                        "skill_name": "project_core",
                        "locked": False,
                        "matched_terms": [],
                        "score": 0,
                        "reason": "fake route",
                        "confidence": 0.6,
                    },
                )()
                self.steps = [
                    PlannedStep(
                        phase=OrchestrationPhase.EXECUTE,
                        skill_name="project_core",
                        reason="planned",
                        prompt="Handle the request.",
                        input_text="smart edit",
                        allowed_tools=["get_project_summary"],
                    )
                ]
                self.nudges = []
                self.planner_mode = "heuristic"
                self.clarification = None

        return Result()

    def fake_run_agent(self, extra_messages=None, persist_history=True) -> None:
        self.session_state.last_operation = "get_project_summary"
        self.session_state.last_decision = {
            "operation": "get_project_summary",
            "code": "project.summary.ready",
            "status": "ok",
            "state": {"project_path": "tmp/project.json"},
            "next_actions": [],
        }

    app.orchestrator.plan = fake_plan
    app._run_agent = MethodType(fake_run_agent, app)

    app.run_once("smart edit")
    output = capsys.readouterr().out

    assert "[pipeline] executing" in output
    assert "[pipeline] done" in output
    assert app._pending_orchestration is None


def test_plan_preview_requires_run_for_execution(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    def fake_plan(user_input, locked_skill=None, session_context=None):
        class Result:
            def __init__(self) -> None:
                self.route = type(
                    "Route",
                    (),
                    {
                        "skill_name": "project_core",
                        "locked": False,
                        "matched_terms": [],
                        "score": 0,
                        "reason": "fake route",
                        "confidence": 0.6,
                    },
                )()
                self.steps = [
                    PlannedStep(
                        phase=OrchestrationPhase.EXECUTE,
                        skill_name="project_core",
                        reason="planned",
                        prompt="Handle the request.",
                        input_text="smart edit",
                        allowed_tools=["get_project_summary"],
                    )
                ]
                self.nudges = []
                self.planner_mode = "llm"
                self.clarification = None

        return Result()

    app.orchestrator.plan = fake_plan

    app.run_once("/plan smart edit")
    preview = capsys.readouterr().out
    assert "[pipeline] plan ready: llm" in preview
    assert app._pending_orchestration is not None

    def fake_run_agent(self, extra_messages=None, persist_history=True) -> None:
        self.session_state.last_operation = "get_project_summary"
        self.session_state.last_decision = {
            "operation": "get_project_summary",
            "code": "project.summary.ready",
            "status": "ok",
            "state": {"project_path": "tmp/project.json"},
            "next_actions": [],
        }

    app._run_agent = MethodType(fake_run_agent, app)
    app.run_once("/run")
    second = capsys.readouterr().out
    assert "[pipeline] executing pending plan" in second
    assert app._pending_orchestration is None
