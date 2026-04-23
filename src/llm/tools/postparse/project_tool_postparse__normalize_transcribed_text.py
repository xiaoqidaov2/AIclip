from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseNormalizeTranscribedTextMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _normalize_transcribed_text(self, text: str) -> str:

        normalized = (text or "").strip()

        if not normalized:

            return ""

        converter = self._get_opencc_converter()

        if converter is None:

            return normalized

        try:

            converted = converter.convert(normalized)

        except Exception:

            return normalized

        return converted.strip() or normalized
