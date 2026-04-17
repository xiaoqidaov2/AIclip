from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional

from .net_asset_tool import NetAssetTool
from .project_tool import ProjectTool
from .tool_registration import ToolRegistration
from .vision_tool import VisionTool
from src.editor_core.contracts import serialize_tool_result


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
            "project": ProjectTool(),
            "net_asset": NetAssetTool(),
            "vision": VisionTool(),
        }
        self._specs: List[ToolSpec] = [
            ToolSpec(
                name="project_core_contract",
                title="Project Core Contract",
                description="Structured guidance for reading tool outputs and staying inside the project core.",
                source="project",
                attr="create_project_from_media",
                doc_file="project_core_contract.txt",
                register=False,
            ),
            ToolSpec(
                name="create_project_from_media",
                title="Project Bootstrap Tool",
                description="Create a project file directly from a raw video or audio source.",
                source="project",
                attr="create_project_from_media",
                doc_file="create_project_from_media.txt",
            ),
            ToolSpec(
                name="transcribe_audio",
                title="Project Subtitle Transcription Tool",
                description="Generate subtitle cues from source audio and store them in the project.",
                source="project",
                attr="transcribe_audio",
                doc_file="transcribe_audio.txt",
            ),
            ToolSpec(
                name="remove_project_silence",
                title="Project Silence Removal Tool",
                description="Rebuild the timeline by removing gaps between subtitle cues.",
                source="project",
                attr="remove_project_silence",
                doc_file="remove_project_silence.txt",
            ),
            ToolSpec(
                name="load_project",
                title="Project Loader Tool",
                description="Load a JSON or XML editing project.",
                source="project",
                attr="load_project",
                doc_file="load_project.txt",
            ),
            ToolSpec(
                name="get_project_summary",
                title="Project Summary Tool",
                description="Return a compact summary of project structure, timeline, and media counts.",
                source="project",
                attr="get_project_summary",
                doc_file="get_project_summary.txt",
            ),
            ToolSpec(
                name="search_project_subtitles",
                title="Project Subtitle Search Tool",
                description="Search subtitle cues by text, speaker, or language without loading the full project payload.",
                source="project",
                attr="search_project_subtitles",
                doc_file="search_project_subtitles.txt",
            ),
            ToolSpec(
                name="list_project_clips",
                title="Project Clip List Tool",
                description="List timeline clips with optional filters such as track, asset, and duration.",
                source="project",
                attr="list_project_clips",
                doc_file="list_project_clips.txt",
            ),
            ToolSpec(
                name="save_project",
                title="Project Saver Tool",
                description="Save a project back to JSON or XML.",
                source="project",
                attr="save_project",
                doc_file="save_project.txt",
            ),
            ToolSpec(
                name="set_project_metadata",
                title="Project Metadata Tool",
                description="Update project metadata in the unified project file.",
                source="project",
                attr="set_project_metadata",
                doc_file="set_project_metadata.txt",
            ),
            ToolSpec(
                name="trim_project_clip",
                title="Project Clip Trim Tool",
                description="Trim a clip inside a project file and save the updated project.",
                source="project",
                attr="trim_project_clip",
                doc_file="trim_project_clip.txt",
            ),
            ToolSpec(
                name="set_project_clip_speed",
                title="Project Clip Speed Tool",
                description="Update clip speed inside a project file.",
                source="project",
                attr="set_project_clip_speed",
                doc_file="set_project_clip_speed.txt",
            ),
            ToolSpec(
                name="add_project_asset",
                title="Project Asset Tool",
                description="Add a media asset into a project file.",
                source="project",
                attr="add_project_asset",
                doc_file="add_project_asset.txt",
            ),
            ToolSpec(
                name="add_project_clip",
                title="Project Clip Insert Tool",
                description="Insert a clip that references an existing asset onto a timeline track at a specific time range.",
                source="project",
                attr="add_project_clip",
                doc_file="add_project_clip.txt",
            ),
            ToolSpec(
                name="add_project_subtitle",
                title="Project Subtitle Add Tool",
                description="Add a subtitle cue into a project file, including spans, position, and margins.",
                source="project",
                attr="add_project_subtitle",
                doc_file="add_project_subtitle.txt",
            ),
            ToolSpec(
                name="update_project_subtitle",
                title="Project Subtitle Update Tool",
                description="Update a subtitle cue inside a project file, including spans, position, and margins.",
                source="project",
                attr="update_project_subtitle",
                doc_file="update_project_subtitle.txt",
            ),
            ToolSpec(
                name="batch_update_project_subtitles",
                title="Project Subtitle Batch Styling Tool",
                description="Update many subtitle cues in one call, including positions, spans, and multiple subtitle effects per cue.",
                source="project",
                attr="batch_update_project_subtitles",
                doc_file="batch_update_project_subtitles.txt",
            ),
            ToolSpec(
                name="add_project_subtitle_span",
                title="Project Subtitle Span Add Tool",
                description="Add a styled span into one subtitle cue.",
                source="project",
                attr="add_project_subtitle_span",
                doc_file="add_project_subtitle_span.txt",
            ),
            ToolSpec(
                name="update_project_subtitle_span",
                title="Project Subtitle Span Update Tool",
                description="Update the text or style of one subtitle span.",
                source="project",
                attr="update_project_subtitle_span",
                doc_file="update_project_subtitle_span.txt",
            ),
            ToolSpec(
                name="remove_project_subtitle_span",
                title="Project Subtitle Span Remove Tool",
                description="Remove one subtitle span from a cue.",
                source="project",
                attr="remove_project_subtitle_span",
                doc_file="remove_project_subtitle_span.txt",
            ),
            ToolSpec(
                name="remove_project_subtitle",
                title="Project Subtitle Remove Tool",
                description="Remove a subtitle cue from a project file.",
                source="project",
                attr="remove_project_subtitle",
                doc_file="remove_project_subtitle.txt",
            ),
            ToolSpec(
                name="prepare_project_render",
                title="Project Render Planning Tool",
                description="Validate a project and produce render readiness state.",
                source="project",
                attr="prepare_project_render",
                doc_file="prepare_project_render.txt",
            ),
            ToolSpec(
                name="add_project_audio_stem",
                title="Project Audio Stem Add Tool",
                description="Add an audio stem reference to a project file.",
                source="project",
                attr="add_project_audio_stem",
                doc_file="add_project_audio_stem.txt",
            ),
            ToolSpec(
                name="update_project_audio_stem",
                title="Project Audio Stem Update Tool",
                description="Update an audio stem in a project file.",
                source="project",
                attr="update_project_audio_stem",
                doc_file="update_project_audio_stem.txt",
            ),
            ToolSpec(
                name="remove_project_audio_stem",
                title="Project Audio Stem Remove Tool",
                description="Remove an audio stem from a project file.",
                source="project",
                attr="remove_project_audio_stem",
                doc_file="remove_project_audio_stem.txt",
            ),
            ToolSpec(
                name="set_project_export_preset",
                title="Project Export Preset Tool",
                description="Create or update an export preset in a project file.",
                source="project",
                attr="set_project_export_preset",
                doc_file="set_project_export_preset.txt",
            ),
            ToolSpec(
                name="plan_project_export",
                title="Project Export Planning Tool",
                description="Plan preview, final, and sidecar export paths for a project.",
                source="project",
                attr="plan_project_export",
                doc_file="plan_project_export.txt",
            ),
            ToolSpec(
                name="render_project",
                title="Project Render Tool",
                description="Render the project timeline to a final video file with subtitle burn-in.",
                source="project",
                attr="render_project",
                doc_file="render_project.txt",
            ),
            ToolSpec(
                name="add_project_effect",
                title="Project Effect Add Tool",
                description="Add a visual effect to a project file.",
                source="project",
                attr="add_project_effect",
                doc_file="add_project_effect.txt",
            ),
            ToolSpec(
                name="update_project_effect",
                title="Project Effect Update Tool",
                description="Update a visual effect in a project file.",
                source="project",
                attr="update_project_effect",
                doc_file="update_project_effect.txt",
            ),
            ToolSpec(
                name="remove_project_effect",
                title="Project Effect Remove Tool",
                description="Remove a visual effect from a project file.",
                source="project",
                attr="remove_project_effect",
                doc_file="remove_project_effect.txt",
            ),
            ToolSpec(
                name="set_project_subtitle_effect",
                title="Project Subtitle Effect Tool",
                description="Attach a visual or animation effect to a subtitle cue. Supports outline, glow, background_box, gradient, fade_in, fade_out, slide_in, slide_out, typewriter, scale_in.",
                source="project",
                attr="set_project_subtitle_effect",
                doc_file="set_project_subtitle_effect.txt",
            ),
            ToolSpec(
                name="remove_project_subtitle_effect",
                title="Project Subtitle Effect Remove Tool",
                description="Remove one or all effects from a subtitle cue.",
                source="project",
                attr="remove_project_subtitle_effect",
                doc_file="remove_project_subtitle_effect.txt",
            ),
            ToolSpec(
                name="add_project_comment",
                title="Project Comment Add Tool",
                description="Add a collaboration comment to a project file.",
                source="project",
                attr="add_project_comment",
                doc_file="add_project_comment.txt",
            ),
            ToolSpec(
                name="update_project_comment",
                title="Project Comment Update Tool",
                description="Update an existing project comment.",
                source="project",
                attr="update_project_comment",
                doc_file="update_project_comment.txt",
            ),
            ToolSpec(
                name="remove_project_comment",
                title="Project Comment Remove Tool",
                description="Remove a collaboration comment from a project file.",
                source="project",
                attr="remove_project_comment",
                doc_file="remove_project_comment.txt",
            ),
            ToolSpec(
                name="lock_project_comment",
                title="Project Comment Lock Tool",
                description="Lock or unlock a collaboration comment.",
                source="project",
                attr="lock_project_comment",
                doc_file="lock_project_comment.txt",
            ),
            ToolSpec(
                name="detect_faces",
                title="Face Detection Tool",
                description="Detect faces in a project's source video and return their bounding box positions per sampled frame.",
                source="project",
                attr="detect_faces",
                doc_file="detect_faces.txt",
            ),
            ToolSpec(
                name="vision_analyze_media",
                title="Vision Analyze Media Tool",
                description=(
                    "Analyze an image or video with an OpenAI-compatible vision model "
                    "(for example DashScope Qwen-VL). Accepts public URL or local file path "
                    "and returns structured analysis text plus usage metadata."
                ),
                source="vision",
                attr="vision_analyze_media",
                doc_file="vision_analyze_media.txt",
            ),
            ToolSpec(
                name="search_net_asset",
                title="Network Asset Search Tool",
                description=(
                    "Search online stock libraries (Pexels, Pixabay, Freesound) "
                    "for free-to-use video, image, or audio assets matching a query. "
                    "Returns a list of results with preview URLs and direct download URLs."
                ),
                source="net_asset",
                attr="search_net_asset",
                doc_file="search_net_asset.txt",
            ),
            ToolSpec(
                name="download_net_asset",
                title="Network Asset Download Tool",
                description=(
                    "Download a stock asset from a URL returned by search_net_asset "
                    "and save it to the local filesystem. "
                    "Returns the local path; register with add_project_asset afterwards."
                ),
                source="net_asset",
                attr="download_net_asset",
                doc_file="download_net_asset.txt",
            ),
        ]
        self._setup()

    def _resolve_callable(self, spec: ToolSpec):
        resource = self._resources[spec.source]
        if isinstance(resource, dict):
            raw_callable = resource[spec.attr]
        else:
            raw_callable = getattr(resource, spec.attr)
        return self._wrap_callable(spec.name, spec.description, raw_callable)

    def _wrap_callable(self, tool_name: str, description: str, raw_callable):
        @wraps(raw_callable)
        def _adapter(*args, **kwargs):
            raw_result = raw_callable(*args, **kwargs)
            return serialize_tool_result(tool_name, raw_result)

        _adapter.__doc__ = description
        _adapter.__name__ = tool_name
        return _adapter

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
            header = f"{spec.title} ({spec.name})"
            if not spec.register:
                header = f"{spec.title} [doc-only]"
            docs.append(f"=== {header} ===")
            doc_text = self.registry.get_tool_doc(spec.name) or spec.description
            docs.append(doc_text)
            docs.append("")
        return "\n".join(docs)

    def build_system_prompt(self, base_prompt: str) -> str:
        return (
            base_prompt.rstrip()
            + "\n\n## Tool Documentation\n"
            + self.get_documentation()
            + "\n\n## Tool Result Contract\n"
            + "Use `decision`, `render_state`, `validation`, `state`, `payload`, and `next_actions` first.\n"
            + "Treat `message` and `summary` as display text only.\n"
            + "For list/dict tool args (such as `spans`, `parameters`), pass native JSON values, not quoted JSON strings.\n"
            + "If `subtitle_source_present` is false and the request depends on subtitles, call `transcribe_audio`.\n"
            + "If the request is to cut silence, use `remove_project_silence` after subtitles exist.\n"
            + "If you need to style, reposition, or add effects to 3 or more subtitles, prefer `batch_update_project_subtitles` instead of many small subtitle tool calls.\n"
            + "If the request targets only a few words in one subtitle, use subtitle span tools instead of replacing the whole cue.\n"
            + "Do not ask the user to guess subtitle content."
        )
