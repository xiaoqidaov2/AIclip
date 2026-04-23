from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseBatchUpdateProjectSubtitlesMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def batch_update_project_subtitles(
        self,
        project_path: str,
        entries: Any,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Apply subtitle styling updates for many cues in one tool call.







        Each entry accepts:



          - subtitle_id (required)



          - start, end, text, speaker, language



          - position, margin_top, margin_bottom, margin_left, margin_right, offset_y



          - spans: list of subtitle span objects



          - effects: list of {kind, parameters, replace?, span_id?}



        """

        try:

            normalized_entries = self._coerce_subtitle_style_entries(entries)

        except (json.JSONDecodeError, ValueError) as exc:

            return self._failure(
                "batch_update_project_subtitles",
                f"Invalid entries: {exc}",
                code="subtitle.batch.invalid_entries",
                path=str(Path(project_path)),
            )

        with self.store.project_lock(project_path):

            project, failure = self._load(project_path)

            if failure:

                return failure

            updated_ids: list[str] = []

            applied_effect_count = 0

            for entry in normalized_entries:

                subtitle_id = str(entry["subtitle_id"])

                spans = entry.get("spans")

                command = UpdateSubtitleCueCommand(
                    cue_id=subtitle_id,
                    start=entry.get("start"),
                    end=entry.get("end"),
                    text=(
                        self._normalize_transcribed_text(entry["text"])
                        if entry.get("text") is not None
                        else None
                    ),
                    spans=(
                        self._normalize_subtitle_spans(
                            subtitle_id,
                            spans,
                        )
                        if spans is not None
                        else None
                    ),
                    speaker=entry.get("speaker"),
                    language=entry.get("language"),
                    position=entry.get("position"),
                    margin_top=entry.get("margin_top"),
                    margin_bottom=entry.get("margin_bottom"),
                    margin_left=entry.get("margin_left"),
                    margin_right=entry.get("margin_right"),
                    offset_y=entry.get("offset_y"),
                )

                result = command.execute(project)

                if not result.ok:

                    return ToolResult(
                        ok=False,
                        status="error",
                        code=result.code,
                        message=result.message,
                        operation="batch_update_project_subtitles",
                        project_id=project.id,
                        project_version=project.version,
                        validation=result.validation,
                        render_state=RenderState(
                            ready=False, blockers=list(result.validation.errors)
                        ),
                        state={
                            "project_path": str(Path(project_path)),
                            "subtitle_id": subtitle_id,
                        },
                        summary=result.message,
                        error=result.message,
                    ).to_dict()

                for effect in entry.get("effects") or []:

                    effect_command = SetSubtitleEffectCommand(
                        cue_id=subtitle_id,
                        kind=str(effect["kind"]),
                        parameters=dict(effect.get("parameters") or {}),
                        replace=bool(effect.get("replace", True)),
                        span_id=effect.get("span_id"),
                    )

                    effect_result = effect_command.execute(project)

                    if not effect_result.ok:

                        return ToolResult(
                            ok=False,
                            status="error",
                            code=effect_result.code,
                            message=effect_result.message,
                            operation="batch_update_project_subtitles",
                            project_id=project.id,
                            project_version=project.version,
                            validation=effect_result.validation,
                            render_state=RenderState(
                                ready=False,
                                blockers=list(effect_result.validation.errors),
                            ),
                            state={
                                "project_path": str(Path(project_path)),
                                "subtitle_id": subtitle_id,
                                "effect_kind": effect.get("kind"),
                            },
                            summary=effect_result.message,
                            error=effect_result.message,
                        ).to_dict()

                    applied_effect_count += 1

                updated_ids.append(subtitle_id)

            saved_path = self.store.save(
                project, output_path or project_path, _already_locked=True
            )

            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.batch.updated",
            message="Subtitle styling batch applied",
            operation="batch_update_project_subtitles",
            project_id=project.id,
            project_version=project.version,
            validation=ValidationSnapshot(
                passed=report.passed,
                warnings=[issue.message for issue in report.warnings],
                errors=[issue.message for issue in report.errors],
            ),
            render_state=RenderState(
                ready=report.passed, blockers=[issue.code for issue in report.errors]
            ),
            artifacts=[ArtifactRef(type="project", path=str(saved_path))],
            state={
                "project_path": str(saved_path),
                "updated_subtitle_ids": updated_ids,
                "updated_subtitle_count": len(updated_ids),
                "applied_effect_count": applied_effect_count,
            },
            summary=f"Applied styling to {len(updated_ids)} subtitles with {applied_effect_count} effect updates",
        ).to_dict()
