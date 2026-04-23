from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseTranscribeAudioMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def transcribe_audio(
        self,
        project_path: str,
        language: Optional[str] = None,
        audio_path: Optional[str] = None,
        model_size: str = "tiny",
        output_path: Optional[str] = None,
        replace_existing: bool = True,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        source_path = self._resolve_media_path(project, audio_path, project_path)

        if source_path is None:

            return self._failure(
                "transcribe_audio",
                "No media source available for transcription",
                code="media.source.missing",
                path=str(Path(project_path)),
            )

        try:

            model = WhisperModel(model_size, device="cpu", compute_type="int8")

            segments_iter, info = model.transcribe(
                str(source_path), language=language, vad_filter=True
            )

            cues: list[SubtitleCue] = []

            for index, segment in enumerate(segments_iter, start=1):

                text = self._normalize_transcribed_text(segment.text or "")

                if not text:

                    continue

                cues.append(
                    SubtitleCue(
                        id=f"sub_{index:04d}",
                        start=float(segment.start),
                        end=float(segment.end),
                        text=text,
                        language=language or getattr(info, "language", None),
                        position="bottom",
                        margin_bottom=0.0,
                        offset_y=0.0,
                        metadata={
                            "source": "transcribe_audio",
                            "segment_index": index,
                        },
                    )
                )

        except Exception as exc:

            return self._failure(
                "transcribe_audio",
                f"Failed to transcribe audio: {exc}",
                code="transcription.failed",
                path=str(source_path),
            )

        if replace_existing:

            project.subtitles = cues

        else:

            project.subtitles.extend(cues)

        project.metadata["subtitle_source_present"] = bool(project.subtitles)

        if language or getattr(info, "language", None):

            project.metadata["subtitle_language"] = language or getattr(
                info, "language", None
            )

        project.bump_version()

        saved_path = self.store.save(project, output_path or project_path)

        report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.transcribed",
            message="Audio transcribed to project subtitles",
            operation="transcribe_audio",
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
            artifacts=[
                ArtifactRef(type="project", path=str(saved_path)),
                ArtifactRef(type="media", path=str(source_path)),
            ],
            state={
                "project_path": str(saved_path),
                "media_path": str(source_path),
                "subtitle_source_present": bool(project.subtitles),
                "subtitle_count": len(project.subtitles),
                "subtitle_text_normalized": self._get_opencc_converter() is not None,
            },
            payload=project.to_dict(),
            next_actions=["remove_project_silence", "prepare_project_render"],
            summary=f"Transcribed {len(cues)} subtitle cues",
        ).to_dict()
