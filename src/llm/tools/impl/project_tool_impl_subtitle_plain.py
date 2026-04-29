from __future__ import annotations

from typing import Any, Dict, Optional

from PIL import Image, ImageDraw


class ProjectToolSubtitlePlainMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _render_plain_subtitle(
        self,
        draw: ImageDraw.ImageDraw,
        image: Image.Image,
        bg_draw: ImageDraw.ImageDraw,
        text_draw: ImageDraw.ImageDraw,
        width: int,
        font: Any,
        font_size: int,
        color: str,
        text: str,
        fx_map: Dict[str, Dict[str, Any]],
        resize_layers: Any,
        get_glow_draw: Any,
        fallback_font: Any = None,
    ) -> None:
        wrap_max_px = max(1, width - font_size)
        wrapped = "\n".join(
            self._wrap_by_pixel_width(self._sanitize_text(text), font, wrap_max_px, draw)
        )
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6, align="center")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = max(0, (width - text_w) // 2)
        y = max(0, (image.height - text_h) // 2)
        if text_h > image.height or text_h < image.height // 2:
            image, draw, bg_draw, text_draw = resize_layers(
                (width, max(text_h + font_size // 2, font_size * 2))
            )
            y = max(0, (image.height - text_h) // 2)
        if "background_box" in fx_map:
            self._draw_background_box(bg_draw, image.width, image.height, fx_map["background_box"])
        outline_p = fx_map.get("outline")
        shadow = outline_p.get("color", "black") if outline_p is not None else "black"
        outline_width = int(outline_p.get("width", 2)) if outline_p is not None else 2
        for dx, dy in self._default_outline_offsets(outline_width):
            self._draw_text_with_fallback(
                text_draw, wrapped, x + dx, y + dy, font, fallback_font, fill=shadow,
                spacing=6, align="center",
            )
        self._draw_text_with_fallback(
            text_draw, wrapped, x, y, font, fallback_font, fill=color,
            spacing=6, align="center",
        )
        glow_p = fx_map.get("glow")
        if glow_p:
            gr, gg, gb, ga = self._parse_color(glow_p.get("color", "white"), 255)
            get_glow_draw(int(glow_p.get("radius", 4))).multiline_text(
                (x, y),
                wrapped,
                font=font,
                fill=(gr, gg, gb, ga),
                spacing=6,
                align="center",
            )

    def _draw_text_with_fallback(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        x: float,
        y: float,
        font: Any,
        fallback_font: Any = None,
        **kwargs: Any,
    ) -> None:
        """Draw text, falling back to *fallback_font* for any missing glyphs.



        If no fallback font is available, or the text contains no missing

        glyphs, this simply calls draw.multiline_text as before.



        """

        if fallback_font is None:
            draw.multiline_text((x, y), text, font=font, **kwargs)
            return

        # Check if any character is missing from the primary font
        has_missing = any(not self._font_has_glyph(font, ch) for ch in text if ch not in ("\n", " "))

        if not has_missing:
            draw.multiline_text((x, y), text, font=font, **kwargs)
            return

        # Per-character fallback: render char-by-char, switching fonts
        # when the primary font lacks a glyph
        cx = float(x)
        cy = float(y)
        spacing = kwargs.get("spacing", 4)
        fill = kwargs.get("fill", "white")
        align = kwargs.get("align", "left")

        lines = text.split("\n")
        line_heights = []
        for line in lines:
            lh = font.size + spacing if hasattr(font, "size") else spacing + 20
            line_heights.append(lh)

        max_line_width = 0
        for line in lines:
            lw = sum(
                draw.textlength(ch, font=self._render_char_with_fallback(font, fallback_font, ch))
                for ch in line
            )
            max_line_width = max(max_line_width, lw)

        for li, line in enumerate(lines):
            line_w = sum(
                draw.textlength(ch, font=self._render_char_with_fallback(font, fallback_font, ch))
                for ch in line
            )
            if align == "center":
                lx = (max_line_width - line_w) / 2 + x
            else:
                lx = float(x)
            for ch in line:
                eff_font = self._render_char_with_fallback(font, fallback_font, ch)
                draw.text((lx, cy), ch, font=eff_font, fill=fill)
                lx += draw.textlength(ch, font=eff_font)
            cy += line_heights[li]
