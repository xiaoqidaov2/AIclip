from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langchain.tools import tool as make_tool


from typing import Any, Dict, Iterator
import json
import re
import uuid


def _compact_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Strip titles and simplify anyOf from a generated JSON schema."""
    schema.pop("title", None)
    schema.pop("description", None)  # duplicated at function level
    props = schema.get("properties", {})
    for prop in props.values():
        prop.pop("title", None)
        if "anyOf" in prop:
            types = [t.get("type") for t in prop["anyOf"] if isinstance(t, dict)]
            if "null" in types and len(types) == 2:
                nullable_type = [t for t in types if t != "null"][0]
                prop.pop("anyOf")
                prop["type"] = nullable_type
    if not schema.get("required"):
        schema.pop("required", None)
    return schema


def _parse_xml_tool_calls(content: str) -> list[dict[str, Any]]:
    """Parse XML-style tool calls (e.g. from mimo-v2.5) into OpenAI-style tool_calls.

    Expected XML format:
        <tool_call>
        <tool_name>generate_animejs_overlay_asset</tool_name>
        <parameters>
        <project_path>/tmp</project_path>
        <asset_id>test</asset_id>
        <code>console.log(1)</code>
        </parameters>
        </tool_call>
    """
    if not content or "<tool_call>" not in content:
        return []

    tool_calls: list[dict[str, Any]] = []
    for block_match in re.finditer(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL):
        block = block_match.group(1)

        name_match = re.search(r"<tool_name>\s*(.*?)\s*</tool_name>", block, re.DOTALL)
        if not name_match:
            continue
        tool_name = name_match.group(1).strip()

        params_match = re.search(r"<parameters>\s*(.*?)\s*</parameters>", block, re.DOTALL)
        args: Dict[str, Any] = {}
        if params_match:
            params_xml = params_match.group(1)
            for tag_match in re.finditer(r"<(\w+)>\s*(.*?)\s*</\1>", params_xml, re.DOTALL):
                key = tag_match.group(1)
                raw = tag_match.group(2).strip()
                # Attempt primitive type coercion
                if raw.lower() == "true":
                    args[key] = True
                elif raw.lower() == "false":
                    args[key] = False
                else:
                    try:
                        if "." in raw:
                            args[key] = float(raw)
                        else:
                            args[key] = int(raw)
                    except ValueError:
                        args[key] = raw

        tool_calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": tool_name,
                "args": args,
                "type": "tool_call",
            }
        )

    return tool_calls


_XML_TOOL_PROMPT = (
    "\n\nWhen you need to call a tool, output the tool call in this exact XML format:\n"
    "<tool_call>\n"
    "<tool_name>TOOL_NAME</tool_name>\n"
    "<parameters>\n"
    "<PARAM_NAME>PARAM_VALUE</PARAM_NAME>\n"
    "</parameters>\n"
    "</tool_call>\n"
    "Do not wrap it in markdown code blocks."
)


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

                base_tool = make_tool(fn)
                # Compact the generated schema to reduce token usage
                try:
                    schema = base_tool.args_schema.model_json_schema()
                    compacted = _compact_schema(schema)
                    base_tool.args_schema = type(
                        base_tool.args_schema.__name__,
                        (base_tool.args_schema,),
                        {"model_json_schema": classmethod(lambda cls, **kw: compacted)},
                    )
                except Exception:
                    pass
                wrapped.append(base_tool)

        return wrapped

    @staticmethod
    def build_agent(model: Any, tools: list, system_prompt: str):
        wrapped_tools = AgentBuilder._wrap_tools(tools)
        bound_model = model.bind_tools(wrapped_tools) if hasattr(model, "bind_tools") else model

        def agent_node(state: MessagesState):
            messages = list(state["messages"])
            if system_prompt:
                effective_prompt = system_prompt + _XML_TOOL_PROMPT
                messages = [SystemMessage(content=effective_prompt)] + messages
            response = bound_model.invoke(messages)

            # Fallback: some models (e.g. mimo-v2.5) emit XML tool calls instead of native tool_calls
            if not response.tool_calls and response.content:
                parsed = _parse_xml_tool_calls(response.content)
                if parsed:
                    response = AIMessage(
                        content=response.content,
                        tool_calls=parsed,
                        id=response.id,
                    )

            return {"messages": [response]}

        base_tool_node = ToolNode(wrapped_tools)

        def tools_node(state: MessagesState):
            result = base_tool_node.invoke(state)
            processed_messages = []
            for msg in result.get("messages", []):
                if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
                    try:
                        data = json.loads(msg.content)
                    except json.JSONDecodeError:
                        data = None

                    if isinstance(data, dict) and data.get("_preview_image_b64"):
                        b64 = data.pop("_preview_image_b64")
                        mime_type = data.pop("_preview_image_mime_type", "image/png")
                        text = json.dumps(data, ensure_ascii=False, default=str)
                        # Return text-only ToolMessage for compatibility
                        processed_messages.append(
                            ToolMessage(
                                content=text,
                                tool_call_id=msg.tool_call_id,
                                name=msg.name,
                            )
                        )
                        # Attach image as a follow-up HumanMessage so the model can see it
                        processed_messages.append(
                            HumanMessage(
                                content=[
                                    {"type": "text", "text": "Here is the preview image from the tool execution:"},
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                                    },
                                ]
                            )
                        )
                        continue
                processed_messages.append(msg)
            return {"messages": processed_messages}

        def should_continue(state: MessagesState):
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        builder = StateGraph(MessagesState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "agent")
        builder.add_conditional_edges(
            "agent",
            should_continue,
            {"tools": "tools", END: END},
        )
        builder.add_edge("tools", "agent")

        return builder.compile()

    @staticmethod
    def stream_agent(
        model: Any, tools: list, system_prompt: str, messages: list
    ) -> Iterator:

        agent = AgentBuilder.build_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
        )

        return agent.stream({"messages": messages})
