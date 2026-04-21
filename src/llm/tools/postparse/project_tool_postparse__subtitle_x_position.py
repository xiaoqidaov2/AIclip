from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSubtitleXPositionMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _subtitle_x_position(
        self, cue: SubtitleCue, image_width: int, video_width: int
    ) -> int:

        margin_left = cue.margin_left

        margin_right = cue.margin_right

        if margin_left is None and isinstance(
            cue.metadata.get("margin_left"), (int, float)
        ):

            margin_left = float(cue.metadata["margin_left"])

        if margin_right is None and isinstance(
            cue.metadata.get("margin_right"), (int, float)
        ):

            margin_right = float(cue.metadata["margin_right"])

        left_margin = int(margin_left if margin_left is not None else 20)

        right_margin = int(margin_right if margin_right is not None else 20)

        available = max(0, video_width - image_width - left_margin - right_margin)

        if available <= 0:

            return max(0, left_margin)

        return max(0, left_margin + available // 2)
