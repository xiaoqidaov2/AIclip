from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseFindSpanRangeMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _find_span_range(
        self,
        full_text: str,
        span_text: str,
        covered_cursor: int = 0,
        single_span: bool = False,
    ) -> tuple[int, int]:
        """Locate a span inside the cue text with tolerant normalization fallback."""

        if not full_text or not span_text:

            return (-1, -1)

        def _search(haystack: str, needle: str, start: int) -> int:

            anchor = max(0, min(start, len(haystack)))

            found = haystack.find(needle, anchor)

            if found < 0 and anchor > 0:

                found = haystack.find(needle)

            return found

        start_idx = _search(full_text, span_text, covered_cursor)

        if start_idx >= 0:

            return (start_idx, min(len(full_text), start_idx + len(span_text)))

        normalized_full = self._normalize_transcribed_text(full_text)

        normalized_span = self._normalize_transcribed_text(span_text)

        if normalized_full and normalized_span:

            normalized_idx = _search(normalized_full, normalized_span, covered_cursor)

            if normalized_idx >= 0:

                return (
                    normalized_idx,
                    min(len(full_text), normalized_idx + len(span_text)),
                )

        if single_span:

            return (0, len(full_text))

        return (-1, -1)
