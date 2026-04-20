import json
from pathlib import Path

from src.editor_core.project import Asset, Clip, Project, Timeline, Track
from src.editor_core.store import ProjectStore
from src.editor_core.workspace import WorkspaceRegistry


def _sample_project() -> Project:
    return Project(
        id="project-1",
        name="Store Test",
        assets=[Asset(id="asset-1", path="media/input.mp4", media_type="video")],
        timeline=Timeline(tracks=[Track(id="track-1", kind="video", clips=[Clip(id="clip-1", asset_id="asset-1", start=0.0, end=2.0)])]),
    )


def test_save_and_load_json_project(tmp_path):
    store = ProjectStore()
    project = _sample_project()
    path = tmp_path / "project.json"

    saved_path = store.save(project, path)
    loaded = store.load(saved_path)

    assert saved_path == path.resolve()
    assert loaded.id == project.id
    assert loaded.timeline.tracks[0].clips[0].id == "clip-1"


def test_save_and_load_xml_project(tmp_path):
    store = ProjectStore()
    project = _sample_project()
    path = tmp_path / "project.xml"

    store.save(project, path)
    loaded = store.load(path)

    assert loaded.name == "Store Test"
    assert loaded.assets[0].id == "asset-1"


def test_mutate_updates_project_and_can_write_to_output_path(tmp_path):
    store = ProjectStore()
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "output.json"
    store.save(_sample_project(), source_path)

    def mutator(project: Project):
        project.name = "Mutated"
        return "done"

    project, result, saved_path = store.mutate(source_path, mutator, output_path=output_path)
    assert result == "done"
    assert project.name == "Mutated"
    assert saved_path == output_path.resolve()

    loaded = store.load(output_path)
    assert loaded.name == "Mutated"


def test_resolve_asset_path_uses_project_workspace(tmp_path):
    store = ProjectStore()
    project_path = tmp_path / "demo" / "project.json"
    resolved = store.resolve_asset_path("media/clip.mp4", project_path)
    assert resolved == (project_path.parent / "media/clip.mp4").resolve()


def test_register_and_find_project_for_media(tmp_path):
    registry = WorkspaceRegistry(base_dir=tmp_path / "workspace-base")
    store = ProjectStore(registry=registry)
    media_path = tmp_path / "source.mp4"
    media_path.write_text("video", encoding="utf-8")

    project_path, created = store.find_or_create_project_for_media(media_path, project_name="Store Registry")
    assert created is True
    assert project_path.name == "project.json"

    project_path.write_text(json.dumps({"id": "project-1", "name": "Store Test"}), encoding="utf-8")
    found = store.find_project_for_media(media_path)
    assert found == project_path


def test_lock_for_path_reuses_same_lock_for_equivalent_paths(tmp_path):
    store = ProjectStore()
    path = tmp_path / "project.json"
    lock_a = store._lock_for_path(path)
    lock_b = store._lock_for_path(Path(str(path)))
    assert lock_a is lock_b

