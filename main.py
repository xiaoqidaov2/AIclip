# pip install -qU "langchain[anthropic]" invoke models
import argparse
import os
import sys
from typing import Any, Optional

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.agent_builder import AgentBuilder
from src.cli.app import CLIApp
from src.coordinator import CoordinatorMode, TaskRegistry
from src.llm import LLMConfig
from src.llm.tools import ToolSetup


class Main:
    def __init__(self, default_skill: Optional[str] = None) -> None:
        self.tool_setup = ToolSetup()
        self.llm_config = LLMConfig()
        self.task_registry_coordinator = TaskRegistry()
        self.default_skill = default_skill
        self._agent_cache: dict[Optional[str], Any] = {}

    def _build_agent(self, skill_name: Optional[str] = None):
        if skill_name in self._agent_cache:
            return self._agent_cache[skill_name]

        tools = self.tool_setup.get_skill_tools(skill_name)
        system_prompt = self.tool_setup.build_system_prompt(
            "You are AiClip's project-core editing assistant.\n"
            "Use tool outputs as the source of truth.",
            skill_name=skill_name,
        )
        agent = AgentBuilder.build_agent(
            model=self.llm_config.create_llm(),
            tools=tools,
            system_prompt=system_prompt,
        )
        self._agent_cache[skill_name] = agent
        return agent

    def _build_coordinator(self, agent, skill_name: Optional[str] = None):
        tools = self.tool_setup.get_skill_tools(skill_name)
        return CoordinatorMode(
            agent=agent,
            tools=tools,
            task_registry=self.task_registry_coordinator,
        )

    def run(self, command: str | None = None) -> None:
        cli_app = CLIApp(
            agent_factory=self._build_agent,
            tool_setup=self.tool_setup,
            llm_config=self.llm_config,
            coordinator_factory=self._build_coordinator,
            initial_skill=self.default_skill,
            enable_llm_plan=False,
        )
        if command:
            cli_app.run_once(command)
            return
        cli_app.run()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="AiClip CLI",
        epilog="Run the interactive CLI, then use /help for in-app commands.",
    )
    parser.add_argument(
        "-c",
        "--command",
        help="Run one command and exit without entering the interactive prompt.",
    )
    parser.add_argument(
        "--skill",
        help="Start with a locked skill, e.g. project_core, asset_discovery, vision_inspection, capcut_finalization, full.",
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    main = Main(default_skill=args.skill)
    if args.command:
        main.run(command=args.command)
    else:
        main.run()
