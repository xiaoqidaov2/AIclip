from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseGetOpenccConverterMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _get_opencc_converter(self):

        if self._opencc_checked:

            return self._opencc_converter

        self._opencc_checked = True

        try:

            from opencc import OpenCC  # type: ignore

        except Exception:

            self._opencc_converter = None

            return None

        try:

            self._opencc_converter = OpenCC("t2s")

        except Exception:

            self._opencc_converter = None

        return self._opencc_converter
