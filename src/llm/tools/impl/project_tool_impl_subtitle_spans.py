from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from PIL import Image, ImageDraw


class ProjectToolSubtitleSpansMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _default_outline_offsets(self, width: int = 2) -> list[tuple[int, int]]:
        return [
            (dx, dy)
            for dx in range(-width, width + 1)
            for dy in range(-width, width + 1)
            if dx != 0 or dy != 0
        ]

    def _render_spanned_subtitle(
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
        spans: list[Any],
        fx_map: Dict[str, Dict[str, Any]],
        resize_layers: Any,
        get_glow_draw: Any,
        fallback_font: Any = None,
    ) -> None:
        full_text = self._sanitize_text(text)
        default_style = {
            "color": color,
            "outline": fx_map.get("outline"),
            "glow": fx_map.get("glow"),
            "bold": False,
            "underline": False,
        }
        char_styles: List[Dict[str, Any]] = [dict(default_style) for _ in full_text]
        covered_cursor = 0
        for span in spans:
            sanitized_span_text = self._sanitize_text(span.text)
            if not sanitized_span_text:
                continue
            span_fx_map = {fx.kind: fx.parameters for fx in getattr(span, "effects", [])}
            style = {
                "color": span.color or color,
                "outline": span_fx_map.get("outline", fx_map.get("outline")),
                "glow": span_fx_map.get("glow", fx_map.get("glow")),
                "bold": bool(getattr(span, "bold", False)),
                "underline": bool(getattr(span, "underline", False)),
            }
            start_idx, end_idx = self._find_span_range(
                full_text,
                sanitized_span_text,
                covered_cursor=covered_cursor,
                single_span=len(spans) == 1,
            )
            if start_idx < 0:
                continue
            for char_index in range(start_idx, end_idx):
                char_styles[char_index] = dict(style)
            covered_cursor = end_idx
        wrap_max_px = max(1, width - font_size)
        wrapped_lines = self._wrap_by_pixel_width(full_text, font, wrap_max_px, draw) or [full_text]
        sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_height = (sample_bbox[3] - sample_bbox[1]) + 6
        total_h = line_height * len(wrapped_lines)
        if total_h > image.height or total_h < image.height // 2:
            image, draw, bg_draw, text_draw = resize_layers(
                (width, max(total_h + font_size // 2, font_size * 2))
            )
        if "background_box" in fx_map:
            self._draw_background_box(bg_draw, image.width, image.height, fx_map["background_box"])
        start_y = int(max(0, (image.height - total_h) // 2))
        full_idx = 0
        for line in wrapped_lines:
            start_y = self._draw_spanned_line(
                draw, text_draw, get_glow_draw, width, font, font_size, color, line, char_styles, full_idx, start_y, fallback_font
            )
            full_idx += len(line)
            while full_idx < len(full_text) and full_text[full_idx] in (" ", "\n"):
                full_idx += 1

    def _draw_spanned_line(
        self,
        draw: ImageDraw.ImageDraw,
        text_draw: ImageDraw.ImageDraw,
        get_glow_draw: Any,
        width: int,
        font: Any,
        font_size: int,
        color: str,
        line: str,
        char_styles: List[Dict[str, Any]],
        full_idx: int,
        start_y: int,
        fallback_font: Any = None,
    ) -> int:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        cx = int(max(0, (width - (line_bbox[2] - line_bbox[0])) // 2))
        cy = int(start_y)
        i = 0
        while i < len(line):
            seg_style, seg_text, i = self._segment_for_line(line, char_styles, full_idx, i, color)
            cx = self._draw_styled_segment(draw, text_draw, get_glow_draw, font, font_size, cx, cy, seg_text, seg_style, fallback_font)
        sample_bbox = draw.textbbox((0, 0), "Ag", font=font)
        return int(start_y + (sample_bbox[3] - sample_bbox[1]) + 6)

    def _segment_for_line(
        self, line: str, char_styles: List[Dict[str, Any]], full_idx: int, start: int, color: str
    ) -> tuple[Dict[str, Any], str, int]:
        fpos = full_idx + start
        seg_style = cast(
            Dict[str, Any],
            char_styles[fpos]
            if fpos < len(char_styles)
            else {"color": color, "outline": None, "glow": None, "bold": False, "underline": False},
        )
        end = start + 1
        while end < len(line):
            fpos_j = full_idx + end
            if fpos_j >= len(char_styles) or char_styles[fpos_j] != seg_style:
                break
            end += 1
        return seg_style, line[start:end], end

    def _draw_styled_segment(
        self,
        draw: ImageDraw.ImageDraw,
        text_draw: ImageDraw.ImageDraw,
        get_glow_draw: Any,
        font: Any,
        font_size: int,
        cx: int,
        cy: int,
        seg_text: str,
        seg_style: Dict[str, Any],
        fallback_font: Any = None,
    ) -> int:
        outline_p = cast(Optional[Dict[str, Any]], seg_style["outline"])
        shadow = outline_p.get("color", "black") if outline_p is not None else "black"
        offsets = self._default_outline_offsets(int(outline_p.get("width", 2)) if outline_p else 2)

        # Check if any char in the segment needs fallback
        needs_fallback = (
            fallback_font is not None
            and any(not self._font_has_glyph(font, ch) for ch in seg_text if ch != " ")
        )

        if needs_fallback:
            # Render char-by-char with per-glyph font fallback
            return self._draw_segment_char_by_char(
                draw, text_draw, get_glow_draw, font, font_size, cx, cy,
                seg_text, seg_style, fallback_font
            )

        for dx, dy in offsets:
            text_draw.text((cx + dx, cy + dy), seg_text, font=font, fill=shadow)
        fill_offsets = [(0, 0)] + ([(1, 0), (0, 1)] if seg_style.get("bold") else [])
        text_fill = cast(Optional[str | float | tuple[int, ...]], seg_style["color"])
        for dx, dy in fill_offsets:
            text_draw.text((cx + dx, cy + dy), seg_text, font=font, fill=text_fill)
        glow_p = cast(Optional[Dict[str, Any]], seg_style["glow"])
        if glow_p:
            gr, gg, gb, ga = self._parse_color(glow_p.get("color", "white"), 255)
            get_glow_draw(int(glow_p.get("radius", 4))).text((cx, cy), seg_text, font=font, fill=(gr, gg, gb, ga))
        if seg_style.get("underline"):
            underline_y = cy + (font.size if hasattr(font, "size") else font_size) + 1
            seg_width = int(draw.textlength(seg_text, font=font))
            text_draw.line([(cx, underline_y), (cx + max(1, seg_width), underline_y)], fill=text_fill, width=2 if seg_style.get("bold") else 1)
        return cx + int(draw.textlength(seg_text, font=font))

    def _draw_segment_char_by_char(
        self,
        draw: ImageDraw.ImageDraw,
        text_draw: ImageDraw.ImageDraw,
        get_glow_draw: Any,
        font: Any,
        font_size: int,
        cx: int,
        cy: int,
        seg_text: str,
        seg_style: Dict[str, Any],
        fallback_font: Any,
    ) -> int:
        """Render a segment char-by-char, switching to fallback font for missing glyphs."""

        outline_p = cast(Optional[Dict[str, Any]], seg_style["outline"])
        shadow = outline_p.get("color", "black") if outline_p is not None else "black"
        offsets = self._default_outline_offsets(int(outline_p.get("width", 2)) if outline_p else 2)
        fill_offsets = [(0, 0)] + ([(1, 0), (0, 1)] if seg_style.get("bold") else [])
        text_fill = cast(Optional[str | float | tuple[int, ...]], seg_style["color"])

        pos_x = cx
        for ch in seg_text:
            eff_font = self._render_char_with_fallback(font, fallback_font, ch)
            # Outline
            for dx, dy in offsets:
                text_draw.text((pos_x + dx, cy + dy), ch, font=eff_font, fill=shadow)
            # Fill
            for dx, dy in fill_offsets:
                text_draw.text((pos_x + dx, cy + dy), ch, font=eff_font, fill=text_fill)
            # Glow
            glow_p = cast(Optional[Dict[str, Any]], seg_style["glow"])
            if glow_p:
                gr, gg, gb, ga = self._parse_color(glow_p.get("color", "white"), 255)
                get_glow_draw(int(glow_p.get("radius", 4))).text(
                    (pos_x, cy), ch, font=eff_font, fill=(gr, gg, gb, ga)
                )
            # Underline
            if seg_style.get("underline"):
                underline_y = cy + (eff_font.size if hasattr(eff_font, "size") else font_size) + 1
                ch_width = int(draw.textlength(ch, font=eff_font))
                text_draw.line(
                    [(pos_x, underline_y), (pos_x + max(1, ch_width), underline_y)],
                    fill=text_fill,
                    width=2 if seg_style.get("bold") else 1,
                )
            pos_x += int(draw.textlength(ch, font=eff_font))

        return pos_x
