from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSubtitleYPositionMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

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

        if position == "top":

            y = top_margin

        elif position == "middle":

            y = max(0, (video_height - image_height) // 2)

        elif (
            position == "below_faces"
            and project
            and "detected_faces" in project.metadata
        ):

            max_face_y = 0

            for frame in project.metadata["detected_faces"]:

                ts = frame["timestamp"]

                # Check frames near the cue's active time

                if cue.start - 0.5 <= ts <= cue.end + 0.5:

                    for face in frame["faces"]:

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
