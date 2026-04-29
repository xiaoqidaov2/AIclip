from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSetProjectSubtitleEffectMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def set_project_subtitle_effect(
        self,
        project_path: str,
        subtitle_id: str,
        kind: str,
        parameters: Optional[Any] = None,
        replace: bool = True,
        output_path: Optional[str] = None,
        span_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Attach a visual or animation effect to a subtitle cue.







        Supported *kind* values



        -----------------------



        Visual (applied to the still subtitle image):



          ``outline``        – text stroke; params: color, width (default 2)



          ``glow``           – luminous halo; params: color (default "white"), radius (default 4)



          ``background_box`` – filled rect behind text; params: color (default "black"), opacity (default 160), padding (default 8)



          ``gradient``       – gradient text fill; params: color_top, color_bottom, direction ("vertical"|"horizontal")







        Animation (applied during render):



          ``fade_in``    – opacity ramp in; params: duration (default 0.3 s)



          ``fade_out``   – opacity ramp out; params: duration (default 0.3 s)



          ``slide_in``   – slide on entry; params: direction ("bottom"|"top"|"left"|"right"), duration, distance (px)



          ``slide_out``  – slide on exit; params: direction, duration, distance



          ``typewriter`` – reveal characters; params: chars_per_second (default 20)



          ``scale_in``   – zoom in; params: duration (default 0.3 s)



        """

        project, failure = self._load(project_path)

        if failure:

            return failure

        try:

            normalized_parameters = self._coerce_json_object(parameters, "parameters")

        except (json.JSONDecodeError, ValueError) as exc:

            return self._failure(
                "set_project_subtitle_effect",
                f"Invalid parameters: {exc}",
                code="subtitle.effect.invalid_parameters",
                path=str(Path(project_path)),
            )

        with self.store.project_lock(project_path):

            project, failure = self._load(project_path)

            if failure:

                return failure

            command = SetSubtitleEffectCommand(
                cue_id=subtitle_id,
                kind=kind,
                parameters=normalized_parameters,
                replace=replace,
                span_id=span_id,
            )

            result = command.execute(project)

            if not result.ok:

                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="set_project_subtitle_effect",
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

            saved_path = self.store.save(
                project, output_path or project_path, _already_locked=True
            )

            report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.effect.set",
            message=f"Effect '{kind}' applied to subtitle {subtitle_id}",
            operation="set_project_subtitle_effect",
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
            state={
                **result.state,
                "project_path": str(saved_path),
                "subtitle_id": subtitle_id,
                "effect_kind": kind,
            },
            payload=self._project_delta_payload(project, project_path),
            summary=f"Applied subtitle effect '{kind}' to cue {subtitle_id}",
        ).to_dict()
