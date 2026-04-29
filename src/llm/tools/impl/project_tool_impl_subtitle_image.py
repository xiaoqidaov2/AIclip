from __future__ import annotations

from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFilter

from src.editor_core.project import SubtitleEffect, SubtitleSpan

from .project_tool_impl_subtitle_plain import ProjectToolSubtitlePlainMixin
from .project_tool_impl_subtitle_spans import ProjectToolSubtitleSpansMixin


class ProjectToolSubtitleImageMixin(
    ProjectToolSubtitlePlainMixin, ProjectToolSubtitleSpansMixin
):
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _make_subtitle_image(
        self,
        text: str,
        width: int,
        font_path: Optional[str],
        font_size: int,
        color: str,
        spans: Optional[list[SubtitleSpan]] = None,
        effects: Optional[list[SubtitleEffect]] = None,
    ) -> Image.Image:
        fx_map: Dict[str, Dict[str, Any]] = {fx.kind: fx.parameters for fx in effects or []}
        image = Image.new("RGBA", (width, max(1, font_size * 4)), (0, 0, 0, 0))
        bg_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        bg_draw = ImageDraw.Draw(bg_layer)
        text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)
        draw = ImageDraw.Draw(image)
        font = self._load_font(font_path, font_size)
        fallback_font = self._load_fallback_font(font_size)
        glow_layers: Dict[int, Image.Image] = {}
        glow_draws: Dict[int, ImageDraw.ImageDraw] = {}

        def get_glow_draw(radius: int) -> ImageDraw.ImageDraw:
            if radius not in glow_layers:
                glow_layers[radius] = Image.new("RGBA", image.size, (0, 0, 0, 0))
                glow_draws[radius] = ImageDraw.Draw(glow_layers[radius])
            return glow_draws[radius]

        def resize_layers(
            new_size: tuple[int, int]
        ) -> tuple[Image.Image, ImageDraw.ImageDraw, ImageDraw.ImageDraw, ImageDraw.ImageDraw]:
            nonlocal image, bg_layer, bg_draw, text_layer, text_draw, draw
            image = Image.new("RGBA", new_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            bg_layer = Image.new("RGBA", new_size, (0, 0, 0, 0))
            bg_draw = ImageDraw.Draw(bg_layer)
            text_layer = Image.new("RGBA", new_size, (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_layer)
            for radius, old_img in list(glow_layers.items()):
                new_img = Image.new("RGBA", new_size, (0, 0, 0, 0))
                new_img.paste(old_img, (0, 0))
                glow_layers[radius] = new_img
                glow_draws[radius] = ImageDraw.Draw(new_img)
            return image, draw, bg_draw, text_draw

        if spans:
            self._render_spanned_subtitle(
                draw,
                image,
                bg_draw,
                text_draw,
                width,
                font,
                font_size,
                color,
                text,
                spans,
                fx_map,
                resize_layers,
                get_glow_draw,
                fallback_font,
            )
        else:
            self._render_plain_subtitle(
                draw,
                image,
                bg_draw,
                text_draw,
                width,
                font,
                font_size,
                color,
                text,
                fx_map,
                resize_layers,
                get_glow_draw,
                fallback_font,
            )
        final_image = bg_layer
        for radius, glow_image in glow_layers.items():
            final_image = Image.alpha_composite(final_image, glow_image.filter(ImageFilter.GaussianBlur(radius)))
        return Image.alpha_composite(final_image, text_layer)
