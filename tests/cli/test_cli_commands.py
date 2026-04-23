from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main as main_module
from src.cli.app import CLIApp


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


def build_app(
    agent_calls: list[str],
) -> CLIApp:
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
    assert "/plan" in captured
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


def test_plan_initializes_planner_skill_on_demand(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/plan")

    captured = capsys.readouterr().out
    assert "LLM planning mode enabled" in captured
    assert agent_calls == []


def test_status_shows_routing_and_planner_mode(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/plan")
    capsys.readouterr()

    app.run_once("/status")

    captured = capsys.readouterr().out
    assert "Active skill: project_core" in captured
    assert "Routing mode: auto" in captured
    assert "Planner mode: llm" in captured


def test_clear_does_not_initialize_runtime_and_resets_planner_mode(capsys) -> None:
    agent_calls: list[str] = []
    app = build_app(agent_calls)

    app.run_once("/plan")
    capsys.readouterr()

    app.run_once("/clear")
    cleared = capsys.readouterr().out

    app.run_once("/status")
    status = capsys.readouterr().out

    assert "[skill] loading" not in cleared
    assert agent_calls == []
    assert "Conversation history cleared." in cleared
    assert "Routing mode: auto" in status
    assert "Planner mode: heuristic" in status


def test_main_reuses_cli_app_across_multiple_run_calls(monkeypatch) -> None:
    FakeCLIAppForMain.instances.clear()
    monkeypatch.setattr(main_module, "CLIApp", FakeCLIAppForMain)

    app = main_module.Main()
    app.run(command="/plan")
    app.run(command="/status")

    assert len(FakeCLIAppForMain.instances) == 1
    assert FakeCLIAppForMain.instances[0].commands == ["/plan", "/status"]
