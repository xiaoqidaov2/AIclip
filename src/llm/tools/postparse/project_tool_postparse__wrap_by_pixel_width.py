from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseWrapByPixelWidthMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _wrap_by_pixel_width(
        self, text: str, font: Any, max_width: int, draw: Any
    ) -> list[str]:
        """Greedy per-character pixel-width wrap.

        Works correctly for CJK (each char ~full-width) and mixed Latin/CJK text."""

        lines: list[str] = []

        for paragraph in text.split("\n"):
            current = ""
            for ch in paragraph:
                candidate = current + ch
                # Use textbbox instead of textlength to avoid C-level crashes with certain fonts/characters
                try:
                    bbox = draw.textbbox((0, 0), candidate, font=font)
                    w = bbox[2] - bbox[0]
                except Exception:
                    w = len(candidate) * (
                        getattr(font, "size", 40) if hasattr(font, "size") else 40
                    )
                if w <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = ch
            if current:
                lines.append(current)
            elif not paragraph:
                lines.append("")
        return lines or [text]
