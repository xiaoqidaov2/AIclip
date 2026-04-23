from langchain.agents import create_agent


from langchain.tools import tool as make_tool


from typing import Any, Iterator


class AgentBuilder:

    @staticmethod
    def _wrap_tools(tools: list) -> list:

        wrapped = []

        for fn in tools:

            if fn is None:

                continue

            if hasattr(fn, "run"):  # already a BaseTool

                wrapped.append(fn)

            else:

                wrapped.append(make_tool(fn))

        return wrapped

    @staticmethod
    def build_agent(model: Any, tools: list, system_prompt: str):

        return create_agent(
            model=model,
            tools=AgentBuilder._wrap_tools(tools),
            system_prompt=system_prompt,
        )

    @staticmethod
    def stream_agent(
        model: Any, tools: list, system_prompt: str, messages: list
    ) -> Iterator:

        agent = create_agent(
            model=model,
            tools=AgentBuilder._wrap_tools(tools),
            system_prompt=system_prompt,
        )

        return agent.stream({"messages": messages})
