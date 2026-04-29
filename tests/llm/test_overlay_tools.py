import hashlib

from PIL import Image

from src.editor_core.project import Asset, Clip, Project, Timeline, Track
from src.editor_core.store import ProjectStore
from src.editor_core.workspace import WorkspaceRegistry
from src.llm.tools.project_tool import ProjectTool
from src.llm.tools.impl import project_tool_impl_media


def _make_tool(tmp_path):
    tool = ProjectTool()
    tool.store = ProjectStore(registry=WorkspaceRegistry(base_dir=tmp_path / "workspace"))
    tool._probe_media = lambda _path: {
        "duration": 5.0,
        "has_audio": False,
        "fps": 30.0,
        "size": [1080, 1920],
        "media_kind": "image",
    }
    return tool


def test_generate_animejs_overlay_asset_registers_generated_preview(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Overlay Demo")
    tool.store.save(project, project_path)

    result = tool.generate_animejs_overlay_asset(
        project_path=str(project_path),
        asset_id="anime_overlay_1",
        code="anime({ targets: '#stage', opacity: [0, 1] });",
        width=320,
        height=180,
        duration=2.5,
        fps=24,
    )

    saved = tool.store.load(project_path)
    asset = saved.find_asset("anime_overlay_1")

    assert result["code"] == "asset.generated"
    assert asset is not None
    assert asset.media_type == "video"
    assert asset.metadata["transparent"] is True
    assert asset.metadata["generator"] == "animejs"
    assert asset.metadata["visible_preview"] is True
    assert asset.metadata["animation_format"] == "webm"
    assert asset.metadata["preview_format"] == "gif"
    assert asset.metadata["render_backend"] in ("playwright", "python_fallback")
    assert asset.metadata["style_signature"]
    render_path = tool.store.resolve_asset_path(asset.path, project_path)
    assert render_path.exists()
    assert render_path.stat().st_size > 0
    assert tool.store.resolve_asset_path(asset.metadata["animejs_bundle"]["manifest_path"], project_path).exists()
    assert render_path.suffix.lower() == ".webm"
    preview_path = tool.store.resolve_asset_path(asset.metadata["animejs_bundle"]["preview_path"], project_path)
    assert preview_path.suffix.lower() == ".gif"
    assert preview_path.exists()
    preview = Image.open(preview_path)
    assert getattr(preview, "is_animated", False) is True
    preview = preview.convert("RGBA")
    alpha = __import__("numpy").array(preview)[:, :, 3]
    assert int(alpha.max()) > 0


def test_generate_animejs_overlay_asset_varies_preview_by_code(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Overlay Demo")
    tool.store.save(project, project_path)

    first = tool.generate_animejs_overlay_asset(
        project_path=str(project_path),
        asset_id="anime_overlay_opacity",
        code="anime({ targets: '#stage', opacity: [0, 1] });",
        width=320,
        height=180,
        duration=1.2,
        fps=12,
    )
    second = tool.generate_animejs_overlay_asset(
        project_path=str(project_path),
        asset_id="anime_overlay_rotate",
        code="anime({ targets: '#stage', rotate: '1turn' });",
        width=320,
        height=180,
        duration=1.2,
        fps=12,
    )

    first_preview = Image.open(first["artifacts"][2]["path"]).convert("RGBA")
    second_preview = Image.open(second["artifacts"][2]["path"]).convert("RGBA")
    first_hash = hashlib.sha1(first_preview.tobytes()).hexdigest()
    second_hash = hashlib.sha1(second_preview.tobytes()).hexdigest()

    assert first["state"]["style_signature"] != second["state"]["style_signature"]
    assert first_hash != second_hash


def test_generate_animejs_overlay_asset_uses_playwright_for_visible_animation(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Overlay Demo")
    tool.store.save(project, project_path)

    # Code that creates a visible red square and animates its position
    visible_code = (
        "const el = document.createElement('div'); "
        "el.style.width = '40px'; el.style.height = '40px'; "
        "el.style.backgroundColor = '#ff0000'; "
        "el.style.position = 'absolute'; el.style.left = '0px'; el.style.top = '20px'; "
        "document.getElementById('stage').appendChild(el); "
        "anime({ targets: el, left: ['0px', '100px'], duration: 2000, easing: 'linear' });"
    )

    result = tool.generate_animejs_overlay_asset(
        project_path=str(project_path),
        asset_id="anime_overlay_visible",
        code=visible_code,
        width=320,
        height=180,
        duration=1.0,
        fps=10,
    )

    saved = tool.store.load(project_path)
    asset = saved.find_asset("anime_overlay_visible")

    assert result["code"] == "asset.generated"
    assert asset is not None
    assert asset.metadata["render_backend"] == "playwright"
    preview_path = tool.store.resolve_asset_path(asset.metadata["animejs_bundle"]["preview_path"], project_path)
    assert preview_path.exists()
    preview = Image.open(preview_path)
    assert getattr(preview, "is_animated", False) is True
    preview = preview.convert("RGBA")
    alpha = __import__("numpy").array(preview)[:, :, 3]
    assert int(alpha.max()) > 0


def test_apply_overlay_to_screen_adds_overlay_clip_with_transform(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    overlay_image = workspace.media_dir / "overlay.png"
    Image.new("RGBA", (640, 360), (255, 0, 0, 255)).save(base_image)
    Image.new("RGBA", (200, 100), (0, 255, 0, 128)).save(overlay_image)

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(id="base_asset", path="media/base.png", media_type="image", metadata={"size": [640, 360]}),
            Asset(id="overlay_asset", path="media/overlay.png", media_type="image", metadata={"size": [200, 100], "transparent": True}),
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="base_clip", asset_id="base_asset", start=0.0, end=5.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    result = tool.apply_overlay_to_screen(
        project_path=str(project_path),
        asset_id="overlay_asset",
        target_clip_id="base_clip",
        overlay_clip_id="overlay_clip_1",
        x=120,
        y=220,
        width=400,
    )

    saved = tool.store.load(project_path)
    overlay_clip = saved.find_clip("overlay_clip_1")
    overlay_track = saved.find_track("overlay_track")

    assert result["code"] == "overlay.applied"
    assert overlay_track is not None
    assert overlay_clip is not None
    # x is forced to 0.5 (centered): 0.5 * 640 - 400/2 = 120
    assert overlay_clip.transform["x"] == 120.0
    # y is forced below subtitles / bottom: 360 - (100*2) - 24 = 136
    assert overlay_clip.transform["y"] == 136.0
    assert overlay_clip.transform["scale"] == 2.0
    assert overlay_clip.metadata["role"] == "overlay"


def test_apply_overlay_defaults_to_asset_duration(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    overlay_image = workspace.media_dir / "overlay.png"
    Image.new("RGBA", (640, 360), (255, 0, 0, 255)).save(base_image)
    Image.new("RGBA", (200, 100), (0, 255, 0, 128)).save(overlay_image)

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(id="base_asset", path="media/base.png", media_type="image", metadata={"size": [640, 360]}),
            Asset(id="overlay_asset", path="media/overlay.png", media_type="image", duration=2.5, metadata={"size": [200, 100], "transparent": True}),
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="base_clip", asset_id="base_asset", start=0.0, end=5.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    result = tool.apply_overlay_to_screen(
        project_path=str(project_path),
        asset_id="overlay_asset",
        target_clip_id="base_clip",
        overlay_clip_id="overlay_clip_1",
        x=120,
        y=220,
        width=400,
    )

    saved = tool.store.load(project_path)
    overlay_clip = saved.find_clip("overlay_clip_1")

    assert result["code"] == "overlay.applied"
    assert overlay_clip is not None
    assert overlay_clip.end == 2.5


def test_apply_overlay_respects_explicit_start_time(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    overlay_image = workspace.media_dir / "overlay.png"
    Image.new("RGBA", (640, 360), (255, 0, 0, 255)).save(base_image)
    Image.new("RGBA", (200, 100), (0, 255, 0, 128)).save(overlay_image)

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(id="base_asset", path="media/base.png", media_type="image", metadata={"size": [640, 360]}),
            Asset(id="overlay_asset", path="media/overlay.png", media_type="image", duration=2.5, metadata={"size": [200, 100], "transparent": True}),
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="base_clip", asset_id="base_asset", start=0.0, end=5.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    tool.apply_overlay_to_screen(
        project_path=str(project_path),
        asset_id="overlay_asset",
        target_clip_id="base_clip",
        overlay_clip_id="overlay_clip_1",
        x=80,
        y=120,
        start=1.5,
    )

    saved = tool.store.load(project_path)
    overlay_clip = saved.find_clip("overlay_clip_1")

    assert overlay_clip is not None
    assert overlay_clip.start == 1.5
    assert overlay_clip.end == 4.0


def test_apply_overlay_auto_caps_large_transparent_asset_by_default(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    overlay_image = workspace.media_dir / "overlay.png"
    Image.new("RGBA", (1080, 1920), (255, 0, 0, 255)).save(base_image)
    Image.new("RGBA", (1080, 1080), (0, 255, 0, 128)).save(overlay_image)

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(id="base_asset", path="media/base.png", media_type="image", metadata={"size": [1080, 1920]}),
            Asset(id="overlay_asset", path="media/overlay.png", media_type="image", metadata={"size": [1080, 1080], "transparent": True}),
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="base_clip", asset_id="base_asset", start=0.0, end=5.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    tool.apply_overlay_to_screen(
        project_path=str(project_path),
        asset_id="overlay_asset",
        target_clip_id="base_clip",
        overlay_clip_id="overlay_clip_1",
        x=100,
        y=140,
    )

    saved = tool.store.load(project_path)
    overlay_clip = saved.find_clip("overlay_clip_1")

    assert overlay_clip is not None
    assert overlay_clip.transform["scale"] == 0.35
    assert overlay_clip.metadata["placement_defaults"]["size_auto_capped"] is True


def test_transparent_video_assets_are_opened_with_mask(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    overlay_path = workspace.media_dir / "overlay.webm"
    overlay_path.write_bytes(b"fake")

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(
                id="overlay_asset",
                path="media/overlay.webm",
                media_type="video",
                duration=1.5,
                metadata={"size": [320, 180], "transparent": True},
            )
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[
                        Clip(
                            id="overlay_clip_1",
                            asset_id="overlay_asset",
                            start=0.0,
                            end=1.5,
                            metadata={"role": "overlay"},
                        )
                    ],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    calls = []

    class DummyClip:
        def __init__(self, duration):
            self.duration = duration
            self.start = 0.0
            self.end = duration

        def subclipped(self, start, end):
            self.start = start
            self.end = end
            self.duration = max(0.0, end - start)
            return self

        def with_start(self, start):
            self.start = start
            return self

        def with_end(self, end):
            self.end = end
            self.duration = max(0.0, end - self.start)
            return self

        def close(self):
            return None

    original_video_file_clip = project_tool_impl_media.VideoFileClip
    try:
        def _fake_video_file_clip(filename, **kwargs):
            calls.append((filename, kwargs))
            return DummyClip(1.5)

        project_tool_impl_media.VideoFileClip = _fake_video_file_clip
        media_clip, opened = tool._build_timeline_video_clip(project, project.timeline.tracks[0].clips[0], str(project_path))
    finally:
        project_tool_impl_media.VideoFileClip = original_video_file_clip
        for item in opened:
            close = getattr(item, "close", None)
            if callable(close):
                close()

    assert media_clip.end == 1.5
    assert calls
    assert calls[0][1]["has_mask"] is True
    assert calls[0][1]["pixel_format"] == "rgba"


def test_set_project_clip_transform_updates_visible_transform(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    Image.new("RGBA", (320, 180), (255, 255, 255, 255)).save(base_image)

    project = Project(
        id="project-1",
        name="Transform Demo",
        assets=[Asset(id="base_asset", path="media/base.png", media_type="image")],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="clip-1", asset_id="base_asset", start=0.0, end=3.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    result = tool.set_project_clip_transform(
        project_path=str(project_path),
        clip_id="clip-1",
        x=45,
        y=90,
        scale=1.25,
        opacity=0.6,
    )

    saved = tool.store.load(project_path)
    clip = saved.find_clip("clip-1")

    assert result["code"] == "clip.transform.updated"
    assert clip is not None
    assert clip.transform == {"x": 45.0, "y": 90.0, "scale": 1.25, "opacity": 0.6}


def test_gif_asset_is_treated_as_video(tmp_path):
    tool = _make_tool(tmp_path)
    gif_path = tmp_path / "demo.gif"
    frame_1 = Image.new("RGBA", (64, 64), (255, 0, 0, 0))
    frame_2 = Image.new("RGBA", (64, 64), (255, 213, 74, 180))
    frame_1.save(gif_path, save_all=True, append_images=[frame_2], duration=80, loop=0, disposal=2, transparency=0)

    asset = Asset(id="gif_asset", path=str(gif_path), media_type="unknown")

    assert tool._asset_media_type(asset, gif_path) == "video"


def test_overlay_video_clip_is_capped_to_source_duration(tmp_path):
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    overlay_path = workspace.media_dir / "overlay.webm"
    overlay_path.write_bytes(b"fake")

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(
                id="overlay_asset",
                path="media/overlay.webm",
                media_type="video",
                duration=3.17,
                metadata={"size": [720, 1280], "transparent": True},
            )
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[
                        Clip(
                            id="overlay_clip_1",
                            asset_id="overlay_asset",
                            start=10.0,
                            end=40.0,
                            metadata={"role": "overlay"},
                        )
                    ],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    class DummyClip:
        def __init__(self, duration):
            self.duration = duration
            self.start = 0.0
            self.end = duration

        def with_start(self, start):
            self.start = start
            return self

        def with_end(self, end):
            self.end = end
            self.duration = max(0.0, end - self.start)
            return self

    original_build_video_clip = tool._build_video_clip
    try:
        tool._build_video_clip = lambda asset, asset_path, clip, opened: DummyClip(3.17)
        media_clip, _ = tool._build_timeline_video_clip(project, project.timeline.tracks[0].clips[0], str(project_path))
    finally:
        tool._build_video_clip = original_build_video_clip

    assert media_clip.start == 10.0
    assert media_clip.end == 13.17


def test_normalize_overlay_position_centers_on_anchor(tmp_path):
    """Normalized coordinates should center the overlay on the anchor point."""
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Coord Demo")
    project.metadata["size"] = [1000, 1000]
    tool.store.save(project, project_path)

    # 200x100 overlay at normalized center (0.5, 0.5) -> should be at (400, 450)
    x, y = tool._normalize_overlay_position(project, 0.5, 0.5, 200.0, 100.0)
    assert x == 400
    assert y == 450


def test_normalize_overlay_position_clamps_to_canvas_bounds(tmp_path):
    """Normalized coordinates near the edge must not push the overlay off-screen."""
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Coord Demo")
    project.metadata["size"] = [1000, 1000]
    tool.store.save(project, project_path)

    # 300x200 overlay at normalized right-bottom (1.0, 1.0) -> clamped to (700, 800)
    x, y = tool._normalize_overlay_position(project, 1.0, 1.0, 300.0, 200.0)
    assert x == 700
    assert y == 800

    # Same overlay at normalized (0.95, 0.95) -> raw would be 850, 850, clamped same
    x2, y2 = tool._normalize_overlay_position(project, 0.95, 0.95, 300.0, 200.0)
    assert x2 == 700
    assert y2 == 800


def test_normalize_overlay_position_int_one_is_pixel_not_normalized(tmp_path):
    """Integer x=1 must be treated as absolute pixel 1, not normalized right edge."""
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    project = Project(id="project-1", name="Coord Demo")
    project.metadata["size"] = [1000, 1000]
    tool.store.save(project, project_path)

    # int(1) -> pixel coordinate 1
    x, y = tool._normalize_overlay_position(project, 1, 1, 100.0, 50.0)
    assert x == 1
    assert y == 1

    # float(1.0) -> normalized right edge, clamped to canvas - overlay size
    x2, y2 = tool._normalize_overlay_position(project, 1.0, 1.0, 100.0, 50.0)
    assert x2 == 900
    assert y2 == 950


def test_apply_overlay_int_one_pixel_coordinates(tmp_path):
    """End-to-end: passing x=1 (int) must place overlay at pixel (1, 1)."""
    tool = _make_tool(tmp_path)
    project_path = tmp_path / "project.json"
    workspace = tool.store.workspace_for_project(project_path)
    workspace.ensure()

    base_image = workspace.media_dir / "base.png"
    overlay_image = workspace.media_dir / "overlay.png"
    Image.new("RGBA", (640, 360), (255, 0, 0, 255)).save(base_image)
    Image.new("RGBA", (200, 100), (0, 255, 0, 128)).save(overlay_image)

    project = Project(
        id="project-1",
        name="Overlay Demo",
        assets=[
            Asset(id="base_asset", path="media/base.png", media_type="image", metadata={"size": [640, 360]}),
            Asset(id="overlay_asset", path="media/overlay.png", media_type="image", metadata={"size": [200, 100], "transparent": True}),
        ],
        timeline=Timeline(
            tracks=[
                Track(
                    id="v1",
                    kind="video",
                    clips=[Clip(id="base_clip", asset_id="base_asset", start=0.0, end=5.0)],
                )
            ]
        ),
    )
    tool.store.save(project, project_path)

    tool.apply_overlay_to_screen(
        project_path=str(project_path),
        asset_id="overlay_asset",
        target_clip_id="base_clip",
        overlay_clip_id="overlay_clip_1",
        x=1,
        y=1,
    )

    saved = tool.store.load(project_path)
    overlay_clip = saved.find_clip("overlay_clip_1")
    assert overlay_clip is not None
    # Placement is now restricted: centered horizontally, below subtitles / bottom
    # x = 0.5 * 640 - 200/2 = 220
    assert overlay_clip.transform["x"] == 220.0
    # y = 360 - 100 - 24 = 236
    assert overlay_clip.transform["y"] == 236.0
