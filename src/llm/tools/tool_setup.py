from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_tools import bash_command, edit_file, grep_file, list_directory, read_file, write_file
from .moviepy_tool import MoviePyTool
from .subtitle_tool import SubtitleTool
from .tool_registration import ToolRegistration


@dataclass(frozen=True)
class ToolSpec:
    name: str
    title: str
    description: str
    source: str
    attr: str
    doc_file: str
    register: bool = True


class ToolSetup:
    """Central tool registry, documentation, and ordered tool access."""

    def __init__(self) -> None:
        self.registry = ToolRegistration()
        self._docs_dir = Path(__file__).resolve().parents[3] / "resources" / "docs"
        self._resources: Dict[str, Any] = {
            "whisper": SubtitleTool(),
            "moviepy": MoviePyTool(),
            "file_tools": {
                "read_file": read_file,
                "edit_file": edit_file,
                "write_file": write_file,
                "grep_file": grep_file,
                "list_directory": list_directory,
                "bash_command": bash_command,
            },
        }
        self._specs: List[ToolSpec] = [
            ToolSpec(
                name="transcribe_audio",
                title="Transcription Tool",
                description="Transcribe audio or video into text.",
                source="whisper",
                attr="transcribe",
                doc_file="transcribe_audio.txt",
            ),
            ToolSpec(
                name="generate_subtitle_srt",
                title="Subtitle Generator Tool (SRT)",
                description="Generate SRT subtitles from audio or video.",
                source="whisper",
                attr="generate_srt",
                doc_file="generate_subtitle_srt.txt",
            ),
            ToolSpec(
                name="generate_subtitle_vtt",
                title="Subtitle Generator Tool (VTT)",
                description="Generate VTT subtitles from audio or video.",
                source="whisper",
                attr="generate_vtt",
                doc_file="generate_subtitle_vtt.txt",
                register=False,
            ),
            ToolSpec(
                name="generate_subtitle",
                title="Subtitle Generator Tool (Unified)",
                description="Generate subtitles in SRT or VTT format.",
                source="whisper",
                attr="generate",
                doc_file="generate_subtitle.txt",
                register=False,
            ),
            ToolSpec(
                name="get_video_info",
                title="Video Info Tool",
                description="Inspect duration, fps, size, and audio presence.",
                source="moviepy",
                attr="get_video_info",
                doc_file="get_video_info.txt",
            ),
            ToolSpec(
                name="trim_video",
                title="Trim Video Tool",
                description="Trim a video segment by time range.",
                source="moviepy",
                attr="trim_video",
                doc_file="trim_video.txt",
            ),
            ToolSpec(
                name="cutout_video",
                title="Cutout Video Tool",
                description="Remove a time range from a video.",
                source="moviepy",
                attr="cutout_video",
                doc_file="cutout_video.txt",
            ),
            ToolSpec(
                name="concatenate_videos",
                title="Concatenate Videos Tool",
                description="Join multiple video files into one output.",
                source="moviepy",
                attr="concatenate_videos",
                doc_file="concatenate_videos.txt",
            ),
            ToolSpec(
                name="resize_video",
                title="Resize Video Tool",
                description="Resize a video by width, height, or scale.",
                source="moviepy",
                attr="resize_video",
                doc_file="resize_video.txt",
            ),
            ToolSpec(
                name="crop_video",
                title="Crop Video Tool",
                description="Crop a region from a video frame.",
                source="moviepy",
                attr="crop_video",
                doc_file="crop_video.txt",
            ),
            ToolSpec(
                name="add_subtitles",
                title="Add Subtitles Tool",
                description="Burn subtitles into a video.",
                source="moviepy",
                attr="add_subtitles",
                doc_file="add_subtitles.txt",
            ),
            ToolSpec(
                name="read_file",
                title="Read File Tool",
                description="Read text from a file.",
                source="file_tools",
                attr="read_file",
                doc_file="read_file.txt",
            ),
            ToolSpec(
                name="edit_file",
                title="Edit File Tool",
                description="Edit text inside a file.",
                source="file_tools",
                attr="edit_file",
                doc_file="edit_file.txt",
            ),
            ToolSpec(
                name="write_file",
                title="Write File Tool",
                description="Write text content to a new or existing file.",
                source="file_tools",
                attr="write_file",
                doc_file="write_file.txt",
            ),
            ToolSpec(
                name="grep_file",
                title="Grep File Tool",
                description="Search for text patterns in files.",
                source="file_tools",
                attr="grep_file",
                doc_file="grep_file.txt",
            ),
            ToolSpec(
                name="list_directory",
                title="Directory Listing Tool",
                description="List files and folders in a directory, with optional hidden items.",
                source="file_tools",
                attr="list_directory",
                doc_file="list_directory.txt",
            ),
            ToolSpec(
                name="bash_command",
                title="Shell Command Tool",
                description="Run shell commands when dedicated tools are unavailable.",
                source="file_tools",
                attr="bash_command",
                doc_file="bash_command.txt",
            ),
        ]
        self._setup()

    def _resolve_callable(self, spec: ToolSpec):
        resource = self._resources[spec.source]
        if isinstance(resource, dict):
            return resource[spec.attr]
        return getattr(resource, spec.attr)

    def _setup(self) -> None:
        for spec in self._specs:
            self.registry.register_tool_doc(spec.name, self._load_doc(spec.doc_file))
            if spec.register:
                self.registry.register_tool(spec.name, self._resolve_callable(spec))

    def _load_doc(self, doc_file: str) -> str:
        doc_path = self._docs_dir / doc_file
        if not doc_path.exists():
            return ""
        return doc_path.read_text(encoding="utf-8")

    @property
    def registered_names(self) -> List[str]:
        return [spec.name for spec in self._specs if spec.register]

    def get_tool(self, name: str):
        tool = self.registry.get_tool(name)
        if tool is None:
            raise KeyError(f"Unknown tool: {name}")
        return tool

    def get_tools(self, names: Optional[List[str]] = None):
        requested = names or self.registered_names
        return [self.get_tool(name) for name in requested]

    def get_documentation(self) -> str:
        docs = []
        for spec in self._specs:
            docs.append(f"=== {spec.title} ({spec.name}) ===")
            doc_text = self.registry.get_tool_doc(spec.name) or spec.description
            docs.append(doc_text)
            docs.append("")
        return "\n".join(docs)

    def build_system_prompt(self, base_prompt: str) -> str:
        return (
            base_prompt.rstrip()
            + "\n\n## Tool Documentation\n"
            + self.get_documentation()
        )
