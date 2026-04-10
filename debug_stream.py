"""Debug script to inspect the actual stream chunk structure from LangGraph agent."""
import sys
import os
import json

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding='utf-8')

from src.llm.tools import ToolRegistration
from src.llm.tools import ASRTool
from src.llm.tools import SubtitleTool
from src.llm.tools import read_file, edit_file, grep_file, bash_command
from src.llm import LLMConfig
from src.agent_builder import AgentBuilder


def main():
    # Setup tools and agent (same as main.py)
    tool_registry = ToolRegistration()
    tool_registry.register_tool("transcribe_audio", ASRTool().transcribe)
    tool_registry.register_tool("generate_subtitle_srt", SubtitleTool().generate_srt)
    tool_registry.register_tool("read_file", read_file)
    tool_registry.register_tool("edit_file", edit_file)
    tool_registry.register_tool("grep_file", grep_file)
    tool_registry.register_tool("bash_command", bash_command)

    llm_config = LLMConfig()
    agent = AgentBuilder.build_agent(
        model=llm_config.create_llm(),
        tools=[
            tool_registry.get_tool("transcribe_audio"),
            tool_registry.get_tool("generate_subtitle_srt"),
            tool_registry.get_tool("read_file"),
            tool_registry.get_tool("edit_file"),
            tool_registry.get_tool("grep_file"),
            tool_registry.get_tool("bash_command"),
        ],
        system_prompt="你是一个多功能命令行助手。",
    )

    # Test message
    messages = [{"role": "user", "content": "帮我将 C:\\Users\\admin\\Documents\\item\\AiClip\\edited_intermediate.mp4 转出字幕"}]

    print("=" * 60)
    print("STREAMING OUTPUT STRUCTURE DEBUG")
    print("=" * 60)

    # Stream and inspect
    chunk_count = 0
    for chunk in agent.stream({"messages": messages}):
        chunk_count += 1
        print(f"\n{'='*60}")
        print(f"CHUNK #{chunk_count}")
        print(f"{'='*60}")
        print(f"Type: {type(chunk)}")
        print(f"Keys: {chunk.keys() if isinstance(chunk, dict) else 'N/A'}")

        if isinstance(chunk, dict):
            for key, value in chunk.items():
                print(f"\n--- Key: {key} ---")
                print(f"Type: {type(value)}")
                if hasattr(value, 'keys'):
                    print(f"Sub-keys: {value.keys() if isinstance(value, dict) else 'N/A'}")

                # Try to extract messages
                if isinstance(value, dict) and 'messages' in value:
                    msgs = value['messages']
                    print(f"\nMessages in '{key}': {len(msgs)}")
                    for i, msg in enumerate(msgs):
                        msg_type = type(msg).__name__
                        print(f"\n  Message #{i+1}: {msg_type}")
                        if hasattr(msg, 'content'):
                            content = msg.content
                            if content and isinstance(content, str) and content.strip():
                                print(f"    Content: {content[:200]}{'...' if len(content) > 200 else ''}")
                        if hasattr(msg, 'tool_calls'):
                            tcs = msg.tool_calls
                            if tcs:
                                print(f"    Tool calls: {tcs}")
                        if hasattr(msg, 'name'):
                            print(f"    Name: {msg.name}")


if __name__ == "__main__":
    main()
