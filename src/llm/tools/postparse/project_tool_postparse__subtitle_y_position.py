from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSubtitleYPositionMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _cue_faces(
        self,
        cue: SubtitleCue,
        project: Optional[Any],
    ) -> list[dict[str, Any]]:
        if not project or "detected_faces" not in project.metadata:
            return []
        faces: list[dict[str, Any]] = []
        for frame in project.metadata["detected_faces"]:
            ts = frame["timestamp"]
            if cue.start - 0.5 <= ts <= cue.end + 0.5:
                faces.extend(frame.get("faces", []))
        return faces

    def _subtitle_y_position(
        self,
        cue: SubtitleCue,
        image_height: int,
        video_height: int,
        project: Optional[Any] = None,
    ) -> int:

        position = (cue.position or cue.metadata.get("position") or "bottom").lower()

        margin_top = cue.margin_top

        margin_bottom = cue.margin_bottom

        if margin_top is None and isinstance(
            cue.metadata.get("margin_top"), (int, float)
        ):

            margin_top = float(cue.metadata["margin_top"])

        if margin_bottom is None and isinstance(
            cue.metadata.get("margin_bottom"), (int, float)
        ):

            margin_bottom = float(cue.metadata["margin_bottom"])

        top_margin = int(
            margin_top if margin_top is not None else max(24, int(video_height * 0.06))
        )

        bottom_margin = int(
            margin_bottom
            if margin_bottom is not None
            else max(24, int(video_height * 0.06))
        )

        cue_faces = self._cue_faces(cue, project)

        if position == "top":

            y = top_margin

        elif position == "middle":

            y = max(0, (video_height - image_height) // 2)
            if cue_faces:
                cue_top = y
                cue_bottom = y + image_height
                overlaps_face = any(
                    cue_bottom > int(face["y"])
                    and cue_top < int(face["y"]) + int(face["h"])
                    for face in cue_faces
                )
                if overlaps_face:
                    min_face_top = min(int(face["y"]) for face in cue_faces)
                    max_face_bottom = max(
                        int(face["y"]) + int(face["h"]) for face in cue_faces
                    )
                    safe_gap = 20
                    candidates: list[int] = []
                    above_y = min_face_top - image_height - safe_gap
                    below_y = max_face_bottom + safe_gap
                    if above_y >= top_margin:
                        candidates.append(above_y)
                    if below_y <= max(0, video_height - image_height):
                        candidates.append(below_y)
                    if candidates:
                        y = min(candidates, key=lambda item: abs(item - cue_top))

        elif (
            position == "below_faces"
            and cue_faces
        ):

            max_face_y = 0

            for face in cue_faces:

                bottom_edge = face["y"] + face["h"]

                if bottom_edge > max_face_y:

                    max_face_y = bottom_edge

            if max_face_y > 0:

                y = min(video_height - image_height, max_face_y + 20)

            else:

                y = max(0, video_height - image_height - bottom_margin)

        else:

            y = max(0, video_height - image_height - bottom_margin)

        offset_y = cue.offset_y

        if offset_y == 0 and isinstance(cue.metadata.get("offset_y"), (int, float)):

            offset_y = float(cue.metadata["offset_y"])

        y = int(y + offset_y)

        return max(0, min(y, max(0, video_height - image_height)))
