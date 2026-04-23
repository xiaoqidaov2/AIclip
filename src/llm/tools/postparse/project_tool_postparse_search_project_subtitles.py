from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSearchProjectSubtitlesMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def search_project_subtitles(
        self,
        project_path: str,
        query: str = "",
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        normalized_query = query.casefold().strip()

        normalized_speaker = (
            speaker.casefold().strip()
            if isinstance(speaker, str) and speaker.strip()
            else None
        )

        normalized_language = (
            language.casefold().strip()
            if isinstance(language, str) and language.strip()
            else None
        )

        matches = []

        for cue in sorted(
            project.subtitles, key=lambda item: (item.start, item.end, item.id)
        ):

            if normalized_query and normalized_query not in cue.text.casefold():

                continue

            if (
                normalized_speaker
                and (cue.speaker or "").casefold() != normalized_speaker
            ):

                continue

            if (
                normalized_language
                and (cue.language or "").casefold() != normalized_language
            ):

                continue

            matches.append(self._subtitle_search_entry(cue))

            if len(matches) >= max(1, int(limit)):

                break

        report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="subtitle.search.completed",
            message="Subtitle search completed",
            operation="search_project_subtitles",
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
            artifacts=[ArtifactRef(type="project", path=str(Path(project_path)))],
            state={
                "project_path": str(Path(project_path)),
                "query": query,
                "speaker": speaker,
                "language": language,
                "match_count": len(matches),
                "subtitle_source_present": bool(project.subtitles),
            },
            payload={
                "project_path": str(Path(project_path)),
                "query": query,
                "speaker": speaker,
                "language": language,
                "matches": matches,
            },
            summary=f"Found {len(matches)} subtitle matches",
        ).to_dict()
