from src.editor_core.project import Asset, AudioStem, Clip, Effect, Project, SubtitleCue, SubtitleSpan, Timeline, Track
from src.editor_core.validation import can_render, validate_project


def test_validate_project_successful_when_references_are_valid():
    project = Project(
        id="project-1",
        name="Valid",
        assets=[],
        timeline=Timeline(tracks=[Track(id="track-1", kind="video", clips=[Clip(id="clip-1", asset_id="a", start=0.0, end=1.0)])]),
    )
    report = validate_project(project)
    assert report.passed is True
    assert report.errors == []


def test_validate_project_reports_missing_required_project_fields():
    project = Project(id="", name="")
    report = validate_project(project)
    assert any(issue.code == "project.id.missing" for issue in report.errors)
    assert any(issue.code == "project.name.missing" for issue in report.errors)
    assert report.passed is False


def test_validate_project_reports_unknown_track_kind_warning():
    project = Project(
        id="project-1",
        name="Track Kind",
        timeline=Timeline(tracks=[Track(id="track-1", kind="mystery", clips=[])]),
    )
    report = validate_project(project)
    assert any(issue.code == "track.kind.unknown" for issue in report.warnings)
    assert report.passed is True


def test_validate_project_reports_invalid_clip_range_and_missing_asset_reference():
    project = Project(
        id="project-1",
        name="Invalid Clip",
        assets=[Asset(id="asset-1", path="media/file.mp4")],
        timeline=Timeline(
            tracks=[Track(id="track-1", kind="video", clips=[Clip(id="clip-1", asset_id="missing-asset", start=1.0, end=1.0)])]
        ),
    )
    report = validate_project(project)
    assert any(issue.code == "clip.range.invalid" for issue in report.errors)
    assert any(issue.code == "clip.asset.missing" for issue in report.errors)
    assert can_render(project) is False


def test_validate_project_reports_audio_stem_and_effect_target_reference_errors():
    project = Project(
        id="project-1",
        name="References",
        timeline=Timeline(tracks=[Track(id="track-1", kind="video", clips=[])]),
        audio_stems=[AudioStem(id="stem-1", role="music", path="/tmp/music.mp3", track_id="missing-track")],
        effects=[Effect(id="effect-1", target_id="missing-target", kind="blur")],
    )
    report = validate_project(project)
    assert any(issue.code == "audio_stem.track.missing" for issue in report.errors)
    assert any(issue.code == "effect.target.missing" for issue in report.errors)


def test_validate_project_reports_subtitle_span_text_mismatch():
    project = Project(
        id="project-1",
        name="Subtitles",
        subtitles=[SubtitleCue(id="cue-1", start=0.0, end=1.0, text="Hello", spans=[SubtitleSpan(id="span-1", text="Hi")])],
    )
    report = validate_project(project)
    assert any(issue.code == "subtitle.spans.text_mismatch" for issue in report.errors)
