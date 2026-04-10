from typing import Any, Dict, Optional


class SessionState:
    """Structured results from the most recent tool calls."""

    def __init__(self) -> None:
        self.last_tool_name: Optional[str] = None
        self.last_tool_result: Optional[Dict[str, Any]] = None
        self.last_subtitle: Optional[Dict[str, Any]] = None
        self.last_transcript: Optional[Dict[str, Any]] = None
        self.last_file_path: Optional[str] = None
        self.last_subtitle_path: Optional[str] = None

    @property
    def has_context(self) -> bool:
        return self.last_subtitle is not None or self.last_transcript is not None

    def clear(self) -> None:
        self.last_tool_name = None
        self.last_tool_result = None
        self.last_subtitle = None
        self.last_transcript = None
        self.last_file_path = None
        self.last_subtitle_path = None

    def update_from_tool(self, tool_name: str, result: Any, tool_args: Optional[Dict[str, Any]] = None) -> None:
        normalized_result = result if isinstance(result, dict) else {"content": result}

        self.last_tool_name = tool_name
        self.last_tool_result = normalized_result

        if tool_args:
            for key in ("audio_path", "file_path", "video_path", "subtitle_path"):
                value = tool_args.get(key)
                if isinstance(value, str):
                    self.last_file_path = value
                    break

        if tool_name in {
            "generate_srt",
            "generate_subtitle_srt",
            "generate_vtt",
            "generate_subtitle_vtt",
            "generate_subtitle",
        }:
            subtitle_path = normalized_result.get("output_path") or normalized_result.get("subtitle_path")
            if isinstance(subtitle_path, str):
                self.last_subtitle_path = subtitle_path

            self.last_subtitle = {
                "format": normalized_result.get("format"),
                "segment_count": normalized_result.get("segment_count"),
                "content": normalized_result.get("subtitle"),
                "language": normalized_result.get("language"),
                "source_path": self.last_file_path,
                "output_path": self.last_subtitle_path,
            }
        elif tool_name in {"transcribe", "transcribe_audio"}:
            self.last_transcript = {
                "text": normalized_result.get("text"),
                "language": normalized_result.get("language"),
                "source_path": self.last_file_path,
            }

    def to_context_prompt(self) -> str:
        lines = ["Current session state:"]

        if self.last_subtitle:
            fmt = str(self.last_subtitle.get("format") or "unknown").upper()
            count = self.last_subtitle.get("segment_count")
            source = self.last_subtitle.get("source_path")
            output_path = self.last_subtitle.get("output_path")
            lines.append(f"- Last subtitle output: {count} segments in {fmt}")
            if source:
                lines.append(f"- Subtitle source: {source}")
            if output_path:
                lines.append(f"- Subtitle file: {output_path}")
            lines.append("- Subtitle content is available for save, edit, format conversion, or burn-in tasks.")

        if self.last_transcript:
            source = self.last_transcript.get("source_path")
            language = self.last_transcript.get("language")
            lines.append(f"- Last transcript language: {language}")
            if source:
                lines.append(f"- Transcript source: {source}")
            lines.append("- Transcript text is available for polishing, correction, or follow-up processing.")

        if not self.has_context:
            lines.append("- No reusable tool output yet.")

        lines.append("- For follow-up requests like save, continue, fix, or convert, prefer the latest results above unless the user asks to regenerate.")
        return "\n".join(lines)
