from typing import Any, Dict, Optional


class SessionState:
    """Store structured results from previous tool calls for follow-up turns."""

    def __init__(self):
        self.last_tool_name: Optional[str] = None
        self.last_tool_result: Optional[Dict[str, Any]] = None
        self.last_subtitle: Optional[Dict[str, Any]] = None
        self.last_transcript: Optional[Dict[str, Any]] = None
        self.last_file_path: Optional[str] = None

    def clear(self) -> None:
        self.last_tool_name = None
        self.last_tool_result = None
        self.last_subtitle = None
        self.last_transcript = None
        self.last_file_path = None

    def update_from_tool(self, tool_name: str, result: Dict[str, Any], tool_args: Optional[Dict[str, Any]] = None) -> None:
        self.last_tool_name = tool_name
        self.last_tool_result = result

        if tool_args:
            file_path = tool_args.get("audio_path") or tool_args.get("file_path")
            if isinstance(file_path, str):
                self.last_file_path = file_path

        if tool_name in {"generate_srt", "generate_subtitle_srt", "generate_vtt", "generate_subtitle_vtt"}:
            self.last_subtitle = {
                "format": result.get("format"),
                "segment_count": result.get("segment_count"),
                "content": result.get("subtitle"),
                "language": result.get("language"),
                "source_path": self.last_file_path,
            }
        elif tool_name in {"transcribe", "transcribe_audio"}:
            self.last_transcript = {
                "text": result.get("text"),
                "language": result.get("language"),
                "source_path": self.last_file_path,
            }

    def to_context_prompt(self) -> str:
        lines = ["当前会话状态："]

        if self.last_subtitle:
            fmt = str(self.last_subtitle.get("format") or "unknown").upper()
            count = self.last_subtitle.get("segment_count")
            source = self.last_subtitle.get("source_path")
            lines.append(f"- 最近生成了 {count} 段 {fmt} 字幕")
            if source:
                lines.append(f"- 字幕来源文件: {source}")
            lines.append("- 字幕内容已经生成并保存在当前会话状态中，可继续保存、修改、转换格式或基于该结果继续操作")

        if self.last_transcript:
            source = self.last_transcript.get("source_path")
            language = self.last_transcript.get("language")
            lines.append(f"- 最近转录了文本，语言: {language}")
            if source:
                lines.append(f"- 转录来源文件: {source}")
            lines.append("- 转录文本已经保存在当前会话状态中，可继续润色、修正错别字或做后续处理")

        if not self.last_subtitle and not self.last_transcript:
            lines.append("- 暂无可复用的工具产出")

        lines.append("- 当用户说“保存”“继续”“修正”“转换”等跟进指令时，优先基于上述最近结果继续处理，而不是重复执行之前的工具，除非用户明确要求重新生成")
        return "\n".join(lines)
