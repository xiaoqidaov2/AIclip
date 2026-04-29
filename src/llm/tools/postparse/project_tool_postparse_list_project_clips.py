from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseListProjectClipsMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def list_project_clips(
        self,
        project_path: str,
        track_id: Optional[str] = None,
        track_kind: Optional[str] = None,
        asset_id: Optional[str] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:

        project, failure = self._load(project_path)

        if failure:

            return failure

        normalized_track_kind = (
            track_kind.casefold().strip()
            if isinstance(track_kind, str) and track_kind.strip()
            else None
        )

        normalized_asset_id = (
            asset_id.strip() if isinstance(asset_id, str) and asset_id.strip() else None
        )

        matches = []

        for track in project.timeline.tracks:

            if track_id and track.id != track_id:

                continue

            if normalized_track_kind and track.kind.casefold() != normalized_track_kind:

                continue

            for clip in sorted(
                track.clips, key=lambda item: (item.start, item.end, item.id)
            ):

                duration = float(clip.end - clip.start)

                if normalized_asset_id and clip.asset_id != normalized_asset_id:

                    continue

                if min_duration is not None and duration < float(min_duration):

                    continue

                if max_duration is not None and duration > float(max_duration):

                    continue

                matches.append(self._clip_listing_entry(project, track, clip))

                if len(matches) >= max(1, int(limit)):

                    break

            if len(matches) >= max(1, int(limit)):

                break

        report = self.store.validate(project)

        return ToolResult(
            ok=report.passed,
            status="ok" if report.passed else "warn",
            code="clip.list.completed",
            message="Clip list ready",
            operation="list_project_clips",
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
                "track_id": track_id,
                "track_kind": track_kind,
                "asset_id": asset_id,
                "match_count": len(matches),
            },
            payload={
                "clips": matches,
            },
            summary=f"Found {len(matches)} clips",
        ).to_dict()
