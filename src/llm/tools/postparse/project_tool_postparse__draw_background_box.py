from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseDrawBackgroundBoxMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _draw_background_box(
        self,
        draw: ImageDraw.ImageDraw,
        img_w: int,
        img_h: int,
        params: Dict[str, Any],
    ) -> None:
        """Fill a semi-transparent rectangle behind the subtitle text."""

        bg_color = params.get("color", "black")

        opacity = int(params.get("opacity", 160))

        padding = int(params.get("padding", 8))

        r, g, b, a = self._parse_color(bg_color, opacity)

        draw.rectangle(
            [max(0, -padding), max(0, -padding), img_w + padding, img_h + padding],
            fill=(r, g, b, a),
        )
