# pip install -qU "langchain[anthropic]" invoke models
import os
import sys

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
    def __init__(self):
        self.tool_setup = ToolSetup()
        self.llm_config = LLMConfig()
        self.task_registry_coordinator = TaskRegistry()

    def run(self):
        tools = self.tool_setup.get_tools()
        system_prompt = self.tool_setup.build_system_prompt(
            "You are a video editing assistant. Use the tools below to help the user complete tasks.\n"
            "Select and combine tools based on the user's request and the context. "
            "When something is unclear, ask the user rather than assuming."
        )

        agent = AgentBuilder.build_agent(
            model=self.llm_config.create_llm(),
            tools=tools,
            system_prompt=system_prompt,
        )

        coordinator = CoordinatorMode(
            agent=agent,
            tools=tools,
            task_registry=self.task_registry_coordinator,
        )

        cli_app = CLIApp(agent, coordinator=coordinator)
        cli_app.run()


if __name__ == "__main__":
    main = Main()
    main.run()
