from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseAddProjectSubtitleMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def add_project_subtitle(
        self,
        project_path: str,
        subtitle_id: str,
        start: float,
        end: float,
        text: str,
        spans: Optional[Any] = None,
        track_id: Optional[str] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        position: Optional[str] = None,
        margin_top: Optional[float] = None,
        margin_bottom: Optional[float] = None,
        margin_left: Optional[float] = None,
        margin_right: Optional[float] = None,
        offset_y: Optional[float] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:

        if spans is not None:

            try:

                spans = self._coerce_json_array(spans, "spans")

            except (json.JSONDecodeError, ValueError) as exc:

                return self._failure(
                    "add_project_subtitle",
                    f"Invalid spans: {exc}",
                    code="subtitle.invalid_spans",
                    path=str(Path(project_path)),
                )

        with self.store.project_lock(project_path):

            project, failure = self._load(project_path)

            if failure:

                return failure

            command = AddSubtitleCueCommand(
                SubtitleCue(
                    id=subtitle_id,
                    start=start,
                    end=end,
                    text=self._normalize_transcribed_text(text),
                    spans=self._normalize_subtitle_spans(subtitle_id, spans or []),
                    track_id=track_id,
                    speaker=speaker,
                    language=language,
                    position=position,
                    margin_top=margin_top,
                    margin_bottom=margin_bottom,
                    margin_left=margin_left,
                    margin_right=margin_right,
                    offset_y=offset_y or 0.0,
                )
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="add_project_subtitle",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(
                        ready=False, blockers=list(result.validation.errors)
                    ),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            self._apply_auto_style_to_subtitles(project, [subtitle_id])

            saved_path = self.store.save(
                project, output_path or project_path, _already_locked=True
            )

            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.added",
            message="Subtitle cue added",
            operation="add_project_subtitle",
            project_id=project.id,
            project_version=project.version,
            changes=result.changes,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed, blockers=[issue.code for issue in report.errors]
            ),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={**result.state, "project_path": str(saved_path)},
            payload=project.to_dict(),
            summary=f"Added subtitle cue {subtitle_id}",
        ).to_dict()
