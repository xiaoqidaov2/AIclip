from src.editor_core.project import Asset, Clip, Project, Timeline, Track
from src.editor_core.store import ProjectStore
from src.editor_core.workspace import WorkspaceRegistry
from src.llm.tools.project_tool import ProjectTool
from src.llm.tools.postparse import project_tool_postparse_transcribe_audio


def _make_tool(tmp_path):
    tool = ProjectTool()
    tool.store = ProjectStore(registry=WorkspaceRegistry(base_dir=tmp_path / "workspace"))
    tool._probe_media = lambda _path: {
        "duration": 3.0,
        "has_audio": True,
        "fps": 30.0,
        "size": [1080, 1920],
        "media_kind": "video",
    }
    return tool


def test_create_project_from_media_imports_source_into_workspace(tmp_path):
    tool = _make_tool(tmp_path)
    source = tmp_path / "source.mp4"

    source.write_bytes(b"video-bytes")

    result = tool.create_project_from_media(
        media_path=str(source), project_name="Workspace Import"
    )

    project_path = result["state"]["project_path"]
    project = tool.store.load(project_path)

    assert result["code"] == "project.created"
    assert project.assets[0].path == "media/source.mp4"
    assert project.assets[0].metadata["workspace_media_path"] == "media/source.mp4"
    assert project.metadata["workspace_media_path"] == "media/source.mp4"
    assert (tool.store.workspace_for_project(project_path).media_dir / "source.mp4").exists()


def test_create_project_from_media_repairs_reused_project_asset_paths(tmp_path):
    tool = _make_tool(tmp_path)
    source = tmp_path / "source.mp4"

    source.write_bytes(b"video-bytes")

    project_path, _ = tool.store.find_or_create_project_for_media(
        source, project_name="Workspace Import"
    )
    project = Project(
        id="project-1",
        name="Workspace Import",
        assets=[Asset(id="asset-1", path=str(source.resolve()), media_type="video")],
        timeline=Timeline(
            tracks=[
                Track(
                    id="track-1",
                    kind="video",
                    clips=[Clip(id="clip-1", asset_id="asset-1", start=0.0, end=3.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    result = tool.create_project_from_media(
        media_path=str(source), project_name="Workspace Import"
    )
    repaired = tool.store.load(project_path)

    assert result["code"] == "project.reused"
    assert repaired.assets[0].path == "media/source.mp4"
    assert repaired.version == 2


def test_resolve_media_path_prefers_workspace_media_when_source_is_external(tmp_path):
    tool = _make_tool(tmp_path)
    source = tmp_path / "source.mp4"

    source.write_bytes(b"video-bytes")

    result = tool.create_project_from_media(
        media_path=str(source), project_name="Workspace Import"
    )
    project_path = result["state"]["project_path"]
    project = tool.store.load(project_path)

    resolved = tool._resolve_media_path(project, project_path=project_path)

    assert resolved == (
        tool.store.workspace_for_project(project_path).media_dir / "source.mp4"
    ).resolve()


def test_transcribe_audio_uses_workspace_media_when_source_is_external(tmp_path, monkeypatch):
    tool = _make_tool(tmp_path)
    source = tmp_path / "source.mp4"

    source.write_bytes(b"video-bytes")

    result = tool.create_project_from_media(
        media_path=str(source), project_name="Workspace Import"
    )
    project_path = result["state"]["project_path"]

    transcribed_paths: list[str] = []

    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def transcribe(self, media_path: str, language=None, vad_filter=True):
            transcribed_paths.append(media_path)
            segments = [type("Segment", (), {"start": 0.0, "end": 1.0, "text": "test subtitle"})()]
            info = type("Info", (), {"language": language or "zh"})()
            return iter(segments), info

    monkeypatch.setattr(
        project_tool_postparse_transcribe_audio,
        "WhisperModel",
        FakeWhisperModel,
    )

    transcribe_result = tool.transcribe_audio(project_path=project_path, replace_existing=True)

    assert transcribe_result["code"] == "subtitle.transcribed"
    assert transcribed_paths == [
        str((tool.store.workspace_for_project(project_path).media_dir / "source.mp4").resolve())
    ]
    assert transcribe_result["state"]["media_path"] == transcribed_paths[0]
