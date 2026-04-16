"""Debug script to inspect the actual stream chunk structure from LangGraph agent."""
import os
import sys

if sys.platform == "win32":
    os.system("chcp 65001 > nul")
    sys.stdout.reconfigure(encoding="utf-8")

from src.agent_builder import AgentBuilder
from src.llm import LLMConfig
from src.llm.tools import ToolSetup


def main():
    tool_setup = ToolSetup()

    llm_config = LLMConfig()
    agent = AgentBuilder.build_agent(
        model=llm_config.create_llm(),
        tools=tool_setup.get_tools(
            [
                "load_project",
                "save_project",
                "set_project_metadata",
                "prepare_project_render",
            ]
        ),
        system_prompt="You are a core project editing assistant.",
    )

    messages = [
        {"role": "user", "content": "Load the project and prepare it for render."}
    ]

    print("=" * 60)
    print("STREAMING OUTPUT STRUCTURE DEBUG")
    print("=" * 60)

    chunk_count = 0
    for chunk in agent.stream({"messages": messages}):
        chunk_count += 1
        print(f"\n{'=' * 60}")
        print(f"CHUNK #{chunk_count}")
        print(f"{'=' * 60}")
        print(f"Type: {type(chunk)}")
        print(f"Keys: {chunk.keys() if isinstance(chunk, dict) else 'N/A'}")

        if isinstance(chunk, dict):
            for key, value in chunk.items():
                print(f"\n--- Key: {key} ---")
                print(f"Type: {type(value)}")
                if hasattr(value, "keys"):
                    print(f"Sub-keys: {value.keys() if isinstance(value, dict) else 'N/A'}")

                if isinstance(value, dict) and "messages" in value:
                    msgs = value["messages"]
                    print(f"\nMessages in '{key}': {len(msgs)}")
                    for i, msg in enumerate(msgs):
                        msg_type = type(msg).__name__
                        print(f"\n  Message #{i + 1}: {msg_type}")
                        if hasattr(msg, "content"):
                            content = msg.content
                            if content and isinstance(content, str) and content.strip():
                                print(f"    Content: {content[:200]}{'...' if len(content) > 200 else ''}")
                        if hasattr(msg, "tool_calls"):
                            tcs = msg.tool_calls
                            if tcs:
                                print(f"    Tool calls: {tcs}")
                        if hasattr(msg, "name"):
                            print(f"    Name: {msg.name}")


if __name__ == "__main__":
    main()
