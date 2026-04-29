from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseSanitizeTextMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _sanitize_text(self, text: str) -> str:
        """Strip characters that typical CJK fonts cannot render (emoji, symbols)



        to prevent tofu-box glyphs appearing in the output.



        Also converts traditional Chinese to simplified Chinese so that fonts

        lacking traditional glyphs (e.g. the bundled WenYue font) can render

        the text correctly instead of showing replacement boxes."""

        import unicodedata

        # Convert traditional Chinese → simplified Chinese before sanitising.

        # This ensures characters like 學/體/國 are converted to 学/体/国

        # which are present in all bundled CJK fonts.

        converter = self._get_opencc_converter()
        if converter is not None:
            try:
                text = converter.convert(text)
            except Exception:
                pass

        result = []

        for ch in text:

            cp = ord(ch)

            # Drop supplementary-plane code points (U+10000+) – most modern emoji live here

            if cp > 0xFFFF:

                continue

            cat = unicodedata.category(ch)

            # Drop surrogates and private-use area

            if cat in ("Cs", "Co"):

                continue

            # Drop "Symbol, Other" (⊠ ☑ ✅ etc.) unless it's CJK punctuation

            if cat == "So" and not (0x3000 <= cp <= 0x303F or 0x2E80 <= cp <= 0x2EFF):

                continue

            result.append(ch)

        return "".join(result)
