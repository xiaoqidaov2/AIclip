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
            "You are a video editing assistant. Use the tools below to help the user complete tasks.\n\n"
            "## Working rules\n"
            "1. Be proactive: when dependencies are missing, try to resolve them first, such as suggesting installation.\n"
            "2. Work in steps: break complex tasks into executable steps.\n"
            "3. Combine tools: prefer chaining dedicated tools, such as generating subtitles before burning them in.\n"
            "4. Prefer dedicated tools over direct bash commands.\n\n"
            "## Common flows\n"
            "- Subtitle generation + burn-in: generate_subtitle_srt(audio_path) -> use bash_command to write .srt -> add_subtitles(video, srt_path, font)\n"
            "- Trim + concatenate: multiple trim_video/cutout_video -> concatenate_videos\n"
            "- Info lookup: get_video_info -> decide the next step"
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
