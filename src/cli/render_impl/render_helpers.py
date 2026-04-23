import json
from typing import Any, Dict


def format_args(args: Dict) -> str:
    parts = []
    for key, value in args.items():
        value_str = str(value)
        if len(value_str) > 60:
            value_str = value_str[:57] + "..."
        parts.append(f"{key}={repr(value_str) if ' ' in value_str else value_str}")
    return ", ".join(parts)


def truncate_text(text: str, max_length: int) -> str:
    return text if len(text) <= max_length else text[: max_length - 3] + "..."


def extract_content(content: Any) -> str:
    if isinstance(content, dict):
        value = content.get("content") or content.get("summary") or content.get("message")
        return str(value).strip() if value is not None else ""
    if content is None:
        return ""
    if isinstance(content, str):
        text = content.strip()
        if not text:
            return ""
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                value = data.get("content") or data.get("summary") or data.get("message")
                if value is not None:
                    return str(value).strip()
        except (json.JSONDecodeError, TypeError):
            pass
        return text
    return str(content).strip()


def extract_summary(content: str, max_summary_length: int) -> str:
    if not content:
        return "完成"
    text = str(content)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            decision = data.get("decision")
            if isinstance(decision, dict):
                parts = [str(decision.get(key)) for key in ("operation", "code", "status") if decision.get(key) not in (None, "")]
                state = decision.get("state")
                if isinstance(state, dict):
                    for key in ("project_path", "output_path", "media_path", "final_path"):
                        value = state.get(key)
                        if value not in (None, ""):
                            parts.append(f"{key}={value}")
                            break
                next_actions = decision.get("next_actions") or []
                if next_actions:
                    parts.append(f"next={','.join(map(str, next_actions[:3]))}")
                if parts:
                    return " | ".join(parts)
            for key in ("code", "status"):
                if key in data:
                    return str(data[key]) if key == "code" else str(data[key])
            if "ok" in data:
                return "成功" if data["ok"] else "失败"
            for key in ("project_path", "output_path", "media_path", "subtitle_path"):
                if key in data and data[key]:
                    return f"{data.get('operation', 'tool')} | {key}={data[key]}"
    except (json.JSONDecodeError, TypeError):
        pass
    return text if len(text) <= max_summary_length else text[: max_summary_length - 3] + "..."
