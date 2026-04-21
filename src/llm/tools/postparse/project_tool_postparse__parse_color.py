from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseParseColorMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _parse_color(
        self, color_str: str, default_a: int = 255
    ) -> tuple[int, int, int, int]:

        c_str = color_str.strip().lower()

        if c_str.startswith("rgba"):

            inner = c_str[4:].strip("() ")

            parts = [p.strip() for p in inner.split(",")]

            if len(parts) >= 3:

                try:

                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])

                    a = default_a

                    if len(parts) >= 4:

                        if "." in parts[3] or float(parts[3]) <= 1.0:

                            a = int(float(parts[3]) * 255)

                        else:

                            a = int(parts[3])

                    return (r, g, b, a)

                except Exception:

                    pass

        from PIL import ImageColor

        try:

            rgba = ImageColor.getrgb(c_str)

            if len(rgba) == 4:

                return (rgba[0], rgba[1], rgba[2], rgba[3])

            return (rgba[0], rgba[1], rgba[2], default_a)

        except Exception:

            return (255, 255, 255, default_a)
