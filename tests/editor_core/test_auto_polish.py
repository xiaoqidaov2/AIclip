from src.editor_core.project import Asset, Project, SubtitleCue, SubtitleEffect, SubtitleSpan
from src.llm.tools.impl.project_tool_impl_time import ProjectToolTimeMixin
from src.llm.tools.postparse.project_tool_postparse_polish_helpers import (
    ProjectToolPostParsePolishHelpersMixin,
)
from src.llm.tools.postparse.project_tool_postparse_silence_helpers import (
    ProjectToolPostParseSilenceHelpersMixin,
)
from src.llm.tools.project_tool import ProjectTool


class FakePolishTool(ProjectToolPostParsePolishHelpersMixin):
    def _normalize_transcribed_text(self, text: str) -> str:
        return " ".join((text or "").strip().split())


class FakeSilenceTool(ProjectToolPostParseSilenceHelpersMixin, ProjectToolTimeMixin):
    pass


def _project_with_canvas() -> Project:
    return Project(
        id="project-1",
        name="Demo",
        assets=[
            Asset(
                id="asset-1",
                path="/tmp/demo.mp4",
                metadata={"size": [1080, 1920]},
            )
        ],
        metadata={"source_media_size": [1080, 1920]},
    )


def test_expand_transcribed_segment_splits_long_text_into_readable_chunks() -> None:
    tool = FakePolishTool()

    segments = tool._expand_transcribed_segment(
        0.0,
        6.0,
        "杩欐槸涓€涓瘮杈冮暱鐨勫瓧骞曞彞瀛愶紝闇€瑕佽嚜鍔ㄦ媶鍒嗘垚鏇撮€傚悎鐭棰戦槄璇荤殑澶氭瀛楀箷锛岄伩鍏嶅崟鏉″瓧骞曡繃闀垮奖鍝嶈鎰熴€?",
    )

    assert len(segments) >= 2
    assert segments[0][0] == 0.0
    assert segments[-1][1] == 6.0
    assert all(item[1] > item[0] for item in segments)
    assert all(len(item[2]) <= 22 for item in segments)


def test_apply_auto_style_to_cue_adds_readability_effects() -> None:
    tool = FakePolishTool()
    project = _project_with_canvas()
    cue = SubtitleCue(id="cue-1", start=0.0, end=1.0, text="涓婇摼鎺?")

    tool._apply_auto_style_to_cue(project, cue)

    effect_kinds = {effect.kind for effect in cue.effects}

    assert cue.position == "middle"
    assert cue.font_size is not None and cue.font_size >= 34
    assert cue.margin_left == cue.margin_right
    assert cue.margin_bottom is not None and cue.margin_bottom > 0
    assert {"outline", "background_box", "fade_in", "fade_out", "scale_in"} <= effect_kinds
    key_spans = [span for span in cue.spans if span.metadata.get("role") == "key_phrase"]
    assert len(key_spans) == 1
    assert len(key_spans[0].text) < len(cue.text)


def test_apply_auto_style_preserves_existing_effect_parameters() -> None:
    tool = FakePolishTool()
    project = _project_with_canvas()
    cue = SubtitleCue(
        id="cue-1",
        start=0.0,
        end=2.0,
        text="淇濈暀宸叉湁鏍峰紡",
        effects=[SubtitleEffect(kind="outline", parameters={"color": "#ff0000", "width": 5})],
    )

    tool._apply_auto_style_to_cue(project, cue)

    outline = next(effect for effect in cue.effects if effect.kind == "outline")

    assert outline.parameters == {"color": "#ff0000", "width": 5}
    assert any(effect.kind == "background_box" for effect in cue.effects)


def test_make_subtitle_image_renders_visible_pixels() -> None:
    tool = ProjectTool()
    cue = SubtitleCue(
        id="cue-1",
        start=0.0,
        end=1.2,
        text="娴嬭瘯瀛楀箷",
        spans=[SubtitleSpan(id="s1", text="娴嬭瘯瀛楀箷")],
    )

    image = tool._make_subtitle_image(cue.text, 620, None, 42, "white", cue.spans, [])
    alpha = __import__("numpy").array(image)[:, :, 3]

    assert int(alpha.max()) > 0
    assert int((alpha > 0).sum()) > 0


def test_middle_position_moves_away_from_detected_faces() -> None:
    tool = ProjectTool()
    cue = SubtitleCue(id="cue-1", start=0.0, end=1.2, text="娴嬭瘯瀛楀箷", position="middle")
    project = Project(
        id="project-1",
        name="Demo",
        metadata={
            "detected_faces": [
                {
                    "timestamp": 0.3,
                    "faces": [{"x": 420, "y": 820, "w": 220, "h": 220}],
                }
            ]
        },
    )

    y_pos = tool._subtitle_y_position(cue, image_height=180, video_height=1920, project=project)

    assert y_pos >= 1060


def test_speech_intervals_merge_small_gaps_for_smoother_cuts() -> None:
    tool = FakeSilenceTool()
    project = Project(
        id="project-1",
        name="Demo",
        subtitles=[
            SubtitleCue(id="cue-1", start=0.0, end=1.0, text="绗竴鍙?"),
            SubtitleCue(id="cue-2", start=1.04, end=2.0, text="绗簩鍙?"),
        ],
    )

    intervals = tool._speech_intervals_from_subtitles(project, 10.0, 0.02)

    assert intervals == [(0.0, 2.02)]
