# pip install -qU "langchain[anthropic]" 调用模型
import os
import sys

# Ensure UTF-8 output for Windows console
if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.agent_builder import AgentBuilder
from src.cli.app import CLIApp
from src.coordinator import CoordinatorMode, TaskRegistry
from src.llm import LLMConfig
from src.llm.tools import ASRTool, MoviePyTool, SubtitleTool, ToolRegistration
from src.llm.tools import bash_command, edit_file, grep_file, read_file


def get_tool_documentation():
    """Collect documentation from all registered tools for injection into system prompt."""
    docs = []

    docs.append("=== 杞綍宸ュ叿 (transcribe_audio) ===")
    docs.append(ASRTool.transcribe.__doc__.strip())
    docs.append("")

    docs.append("=== 瀛楀箷鐢熸垚宸ュ叿 (generate_subtitle_srt) ===")
    docs.append("SRT 鏍煎紡:")
    docs.append(SubtitleTool.generate_srt.__doc__.strip())
    docs.append("")
    docs.append("VTT 鏍煎紡:")
    docs.append(SubtitleTool.generate_vtt.__doc__.strip())
    docs.append("")
    docs.append("缁熶竴鎺ュ彛:")
    docs.append(SubtitleTool.generate.__doc__.strip())
    docs.append("")

    docs.append("=== 瑙嗛淇℃伅宸ュ叿 (get_video_info) ===")
    docs.append(MoviePyTool.get_video_info.__doc__.strip())
    docs.append("")

    docs.append("=== 鎴彇瑙嗛宸ュ叿 (trim_video) ===")
    docs.append(MoviePyTool.trim_video.__doc__.strip())
    docs.append("")

    docs.append("=== 鍒犻櫎鐗囨宸ュ叿 (cutout_video) ===")
    docs.append(MoviePyTool.cutout_video.__doc__.strip())
    docs.append("")

    docs.append("=== 鎷兼帴瑙嗛宸ュ叿 (concatenate_videos) ===")
    docs.append(MoviePyTool.concatenate_videos.__doc__.strip())
    docs.append("")

    docs.append("=== 璋冩暣鍒嗚鲸鐜囧伐鍏?(resize_video) ===")
    docs.append(MoviePyTool.resize_video.__doc__.strip())
    docs.append("")

    docs.append("=== 瑁佸壀鐢婚潰宸ュ叿 (crop_video) ===")
    docs.append(MoviePyTool.crop_video.__doc__.strip())
    docs.append("")

    docs.append("=== 瀛楀箷鐑у綍宸ュ叿 (add_subtitles) ===")
    docs.append(MoviePyTool.add_subtitles.__doc__.strip())
    docs.append("")

    docs.append("=== 鏂囦欢璇诲彇宸ュ叿 (read_file) ===")
    docs.append(read_file.__doc__.strip())
    docs.append("")

    docs.append("=== 鏂囦欢缂栬緫宸ュ叿 (edit_file) ===")
    docs.append(edit_file.__doc__.strip())
    docs.append("")

    docs.append("=== 鏂囦欢鎼滅储宸ュ叿 (grep_file) ===")
    docs.append(grep_file.__doc__.strip())
    docs.append("")

    docs.append("=== Shell鍛戒护宸ュ叿 (bash_command) ===")
    docs.append(bash_command.__doc__.strip())
    docs.append("")

    return "\n".join(docs)


class Main:
    def __init__(self):
        self.tool_registry = ToolRegistration()
        self.moviepy_tool = MoviePyTool()
        self.asr_tool = ASRTool()
        self.subtitle_tool = SubtitleTool()

        self.tool_registry.register_tool("transcribe_audio", self.asr_tool.transcribe)
        self.tool_registry.register_tool("generate_subtitle_srt", self.subtitle_tool.generate_srt)
        self.tool_registry.register_tool("get_video_info", self.moviepy_tool.get_video_info)
        self.tool_registry.register_tool("trim_video", self.moviepy_tool.trim_video)
        self.tool_registry.register_tool("cutout_video", self.moviepy_tool.cutout_video)
        self.tool_registry.register_tool("concatenate_videos", self.moviepy_tool.concatenate_videos)
        self.tool_registry.register_tool("resize_video", self.moviepy_tool.resize_video)
        self.tool_registry.register_tool("crop_video", self.moviepy_tool.crop_video)
        self.tool_registry.register_tool("add_subtitles", self.moviepy_tool.add_subtitles)
        self.tool_registry.register_tool("read_file", read_file)
        self.tool_registry.register_tool("edit_file", edit_file)
        self.tool_registry.register_tool("grep_file", grep_file)
        self.tool_registry.register_tool("bash_command", bash_command)

        # Load environment variables from .env and create LLM config
        self.llm_config = LLMConfig()
        self.task_registry_coordinator = TaskRegistry()

    def run(self):
        tool_docs = get_tool_documentation()
        tools = [
            self.tool_registry.get_tool("transcribe_audio"),
            self.tool_registry.get_tool("generate_subtitle_srt"),
            self.tool_registry.get_tool("get_video_info"),
            self.tool_registry.get_tool("trim_video"),
            self.tool_registry.get_tool("cutout_video"),
            self.tool_registry.get_tool("concatenate_videos"),
            self.tool_registry.get_tool("resize_video"),
            self.tool_registry.get_tool("crop_video"),
            self.tool_registry.get_tool("add_subtitles"),
            self.tool_registry.get_tool("read_file"),
            self.tool_registry.get_tool("edit_file"),
            self.tool_registry.get_tool("grep_file"),
            self.tool_registry.get_tool("bash_command"),
        ]
        agent = AgentBuilder.build_agent(
            model=self.llm_config.create_llm(),
            tools=tools,
            system_prompt=(
                "你是一个视频剪辑助手。你可以使用以下工具帮助用户完成任务。\n\n"
                "## 工作原则\n"
                "1. 主动推进：遇到依赖缺失时先尝试解决，例如提示安装依赖。\n"
                "2. 分步执行：把复杂任务拆成多个可执行步骤。\n"
                "3. 组合使用：优先串联专用工具，例如先生成字幕再烧录。\n"
                "4. 优先使用专用工具，而不是直接依赖 bash 命令。\n\n"
                "## 常见流程\n"
                "- 字幕生成+烧录：generate_subtitle_srt(audio_path) -> 用 bash_command 写入 .srt -> add_subtitles(video, srt_path, font)\n"
                "- 剪辑+拼接：多个 trim_video/cutout_video -> concatenate_videos\n"
                "- 信息查询：get_video_info -> 再决定后续操作\n\n"
                "## 工具列表\n"
                f"{tool_docs}"
            ),
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
