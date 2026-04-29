from __future__ import annotations

from .project_tool_postparse_common import *


class ProjectToolPostParseLoadFontMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _load_font(self, font_path: Optional[str], font_size: int):
        """Load a font for subtitle rendering.







        Priority:



        1. Explicitly specified font_path



        2. Environment variable AICLIP_SUBTITLE_FONT



        3. Bundled fonts in resources/fonts (WenYue preferred)



        4. Windows system fonts (CJK compatible)



        5. Default font



        """

        fonts_dir = Path(__file__).resolve().parents[4] / "resources" / "fonts"

        candidates = []

        configured_font = os.getenv("AICLIP_SUBTITLE_FONT")

        # Windows system fonts - fallback for CJK compatibility

        windows_font_candidates = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),  # Microsoft YaHei (微软雅黑)
            Path(r"C:\Windows\Fonts\msyhbd.ttc"),  # Microsoft YaHei Bold
            Path(r"C:\Windows\Fonts\simhei.ttf"),  # SimHei (黑体)
            Path(r"C:\Windows\Fonts\simsun.ttc"),  # SimSun (宋体)
            Path(r"C:\Windows\Fonts\msjh.ttc"),  # Microsoft JhengHei
        ]

        def _append_candidate(path_value: Path) -> None:

            if path_value not in candidates:

                candidates.append(path_value)

        # Priority 1: Explicitly specified font

        if font_path:

            _append_candidate(Path(font_path))

        # Priority 2: Environment variable

        if configured_font:

            _append_candidate(Path(configured_font))

        # Priority 3: Bundled fonts - WenYue first (now works with Pillow 12+)

        if fonts_dir.exists():

            bundled_candidates = [
                fonts_dir / "WenYue-XinQingNianTi-W8-J-2.otf",  # Preferred
                fonts_dir / "simhei.ttf",
                fonts_dir / "simsun.ttc",
                fonts_dir / "NotoSansCJK-Regular.ttc",
            ]

            for candidate in bundled_candidates:

                if candidate.exists():

                    _append_candidate(candidate)

        # Priority 4: Windows system fonts (fallback)

        for candidate in windows_font_candidates:

            if candidate.exists():

                _append_candidate(candidate)

        for candidate in candidates:

            try:

                return ImageFont.truetype(str(candidate), font_size)

            except Exception:

                continue

        return ImageFont.load_default()

    def _load_fallback_font(self, font_size: int):
        """Load a fallback font with broad CJK coverage for per-glyph fallback.



        Skips the primary bundled font (WenYue) and prefers system fonts

        that have full traditional + simplified Chinese coverage.



        """

        fonts_dir = Path(__file__).resolve().parents[4] / "resources" / "fonts"

        candidates = []

        # Prefer system fonts with broad CJK coverage first

        windows_font_candidates = [
            Path(r"C:\Windows\Fonts\msyh.ttc"),  # Microsoft YaHei
            Path(r"C:\Windows\Fonts\msjh.ttc"),  # Microsoft JhengHei (traditional)
            Path(r"C:\Windows\Fonts\simhei.ttf"),  # SimHei
            Path(r"C:\Windows\Fonts\simsun.ttc"),  # SimSun
        ]

        for candidate in windows_font_candidates:
            if candidate.exists():
                candidates.append(candidate)

        # Then bundled fonts (skip WenYue - it's the primary that may lack glyphs)

        if fonts_dir.exists():
            bundled = [
                fonts_dir / "NotoSansCJK-Regular.ttc",
                fonts_dir / "simhei.ttf",
                fonts_dir / "simsun.ttc",
            ]
            for candidate in bundled:
                if candidate.exists() and candidate not in candidates:
                    candidates.append(candidate)

        for candidate in candidates:
            try:
                return ImageFont.truetype(str(candidate), font_size)
            except Exception:
                continue

        return None

    def _font_has_glyph(self, font: Any, ch: str) -> bool:
        """Check whether *font* contains a usable glyph for *ch*.



        Compares the rendered bbox of *ch* against the .notdef (missing

        glyph) bbox.  If they are identical the character is missing.



        """

        try:
            char_bbox = font.getbbox(ch)
            # Render a known-missing character to get the .notdef reference bbox
            notdef_bbox = font.getbbox("\uffff")
            return char_bbox != notdef_bbox
        except Exception:
            return True

    def _render_char_with_fallback(
        self,
        primary_font: Any,
        fallback_font: Any,
        ch: str,
    ) -> Any:
        """Return the font that can render *ch*, preferring *primary_font*.



        Falls back to *fallback_font* if the primary lacks the glyph.



        """

        if fallback_font is not None and not self._font_has_glyph(primary_font, ch):
            return fallback_font
        return primary_font
