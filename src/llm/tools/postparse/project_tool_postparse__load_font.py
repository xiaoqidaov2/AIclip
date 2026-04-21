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
