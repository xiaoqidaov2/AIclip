from typing import Any, Dict

from .render_helpers import extract_content, extract_summary, format_args, truncate_text


def process_stream_message(renderer: Any, msg: Any, tool_calls_seen: set[str], current_content: str) -> str:
    if type(msg).__name__ == "AIMessage":
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tool_call in tool_calls:
                call_id = tool_call.get("id", "")
                if call_id not in tool_calls_seen:
                    tool_calls_seen.add(call_id)
                    show_tool_call(renderer, tool_call.get("name", "unknown"), tool_call.get("args", {}))
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.strip():
            current_content = content
    return current_content


def process_tool_result(renderer: Any, msg: Any) -> None:
    name = getattr(msg, "name", "tool")
    content = getattr(msg, "content", "")
    summary = extract_summary(content, renderer.MAX_SUMMARY_LENGTH)
    content_text = extract_content(content)
    renderer.clear_status()
    if renderer.verbose:
        print(f"\n{renderer.theme.success('└─')} {renderer.theme.label(f'[{name}]')} 完成")
        print(f"   {renderer.theme.muted('结果:')} {content}")
    else:
        print(f"\n{renderer.theme.success('└─')} {renderer.theme.label(f'[{name}]')} {summary}")
    if content_text and content_text != summary:
        print(f"   {renderer.theme.muted('Content:')} {truncate_text(content_text, renderer.MAX_SUMMARY_LENGTH)}")


def show_tool_call(renderer: Any, name: str, args: Dict) -> None:
    renderer.clear_status()
    print(f"\n{renderer.theme.info('├─')} 调用工具: {renderer.theme.accent(name)}")
    if args:
        print(f"{renderer.theme.info('│  ')} 参数: {renderer.theme.muted(format_args(args))}")
    if name in renderer.STATIC_PROGRESS_TOOLS:
        print(renderer.theme.info(f"[tool] {name} running; MoviePy progress bar follows below."))
    else:
        renderer.show_status(f"Executing {name}...")
    renderer.last_tool_calls.append({"name": name, "args": args})


def render_response(renderer: Any, response: Any) -> str:
    renderer.show_status("Thinking...")
    messages = response.get("messages", []) if isinstance(response, dict) else []
    if not messages:
        renderer.clear_status()
        print(renderer.theme.warn("没有响应消息"))
        return ""
    final_content = ""
    for msg in messages:
        msg_type = type(msg).__name__
        if msg_type == "AIMessage":
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                for tool_call in tool_calls:
                    show_tool_call(renderer, tool_call.get("name", "unknown"), tool_call.get("args", {}))
            content = getattr(msg, "content", "")
            if content:
                final_content = content
        elif msg_type == "ToolMessage":
            process_tool_result(renderer, msg)
    renderer.clear_status()
    if final_content:
        print(f"\n{renderer.theme.title(final_content)}")
    return final_content


def render_stream_simple(stream_iterator_provider: Any, verbose: bool = False) -> str:
    from ..render import CLIRenderer
    renderer = CLIRenderer()
    renderer.set_verbose(verbose)
    return renderer.render_stream(stream_iterator_provider)[0]
