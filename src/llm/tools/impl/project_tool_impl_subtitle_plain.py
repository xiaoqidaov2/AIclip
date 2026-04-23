from __future__ import annotations

from typing import Any, Dict

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
            resize_layers((width, max(text_h + font_size // 2, font_size * 2)))
            y = max(0, (image.height - text_h) // 2)
        if "background_box" in fx_map:
            self._draw_background_box(bg_draw, image.width, image.height, fx_map["background_box"])
        outline_p = fx_map.get("outline")
        shadow = outline_p.get("color", "black") if outline_p is not None else "black"
        outline_width = int(outline_p.get("width", 2)) if outline_p is not None else 2
        for dx, dy in self._default_outline_offsets(outline_width):
            text_draw.multiline_text(
                (x + dx, y + dy),
                wrapped,
                font=font,
                fill=shadow,
                spacing=6,
                align="center",
            )
        text_draw.multiline_text((x, y), wrapped, font=font, fill=color, spacing=6, align="center")
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