from __future__ import annotations

import math

import numpy as np

from .project_tool_postparse_common import *


class ProjectToolPostParseGenerateAnimejsOverlayAssetMixin:
    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def _overlay_file_stem(self, asset_id: str, code: str) -> str:
        digest = hashlib.sha1(code.encode("utf-8")).hexdigest()[:10]
        safe_asset_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in asset_id).strip("_") or "overlay"
        return f"{safe_asset_id}_{digest}"

    def _overlay_style_profile(self, asset_id: str, label: str, code: str, width: int, height: int) -> Dict[str, Any]:
        digest = hashlib.sha1(f"{asset_id}:{label}:{code}".encode("utf-8")).digest()
        width = max(1, int(width))
        height = max(1, int(height))
        style_index = digest[0] % 4
        accent = (
            160 + digest[1] % 96,
            120 + digest[2] % 120,
            48 + digest[3] % 160,
            128 + digest[4] % 96,
        )
        glow = (
            accent[0],
            accent[1],
            accent[2],
            max(48, accent[3] // 2),
        )
        return {
            "signature": hashlib.sha1(f"{asset_id}:{label}:{code}".encode("utf-8")).hexdigest()[:16],
            "style_index": style_index,
            "accent": accent,
            "glow": glow,
            "phase_offset": (digest[5] / 255.0) * math.tau,
            "center_x": 0.35 + (digest[6] / 255.0) * 0.3,
            "center_y": 0.30 + (digest[7] / 255.0) * 0.4,
            "orbit_radius": int(min(width, height) * (0.16 + (digest[8] / 255.0) * 0.20)),
            "orbit_jitter": int(min(width, height) * (0.02 + (digest[9] / 255.0) * 0.05)),
            "dot_count": 8 + digest[10] % 12,
            "dot_size": 4 + digest[11] % 8,
            "bar_count": 4 + digest[12] % 6,
            "bar_height": 12 + digest[13] % 18,
            "bar_swing": 0.08 + (digest[14] / 255.0) * 0.24,
            "card_width_ratio": 0.20 + (digest[15] / 255.0) * 0.30,
            "card_height_ratio": 0.08 + (digest[16] / 255.0) * 0.14,
            "card_scale_swing": 0.08 + (digest[17] / 255.0) * 0.18,
            "point_count": 3 + digest[18] % 4,
            "point_spread": 0.10 + (digest[19] / 255.0) * 0.18,
            "size_ratio": 0.08 + (digest[0] / 255.0) * 0.10,
        }

    def generate_animejs_overlay_asset(
        self,
        project_path: str,
        asset_id: str,
        code: str,
        width: int = 640,
        height: int = 640,
        duration: float = 3.0,
        fps: float = 30.0,
        label: str = "Anime.js Overlay",
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.store.project_lock(project_path):
            project, failure = self._load(project_path)
            if failure:
                return failure

            workspace = self.store.workspace_for_project(project_path)
            workspace.ensure()
            bundle_dir = workspace.media_dir / "generated_overlays"
            bundle_dir.mkdir(parents=True, exist_ok=True)

            file_stem = self._overlay_file_stem(asset_id, code)
            html_path = bundle_dir / f"{file_stem}.html"
            js_path = bundle_dir / f"{file_stem}.js"
            manifest_path = bundle_dir / f"{file_stem}.json"
            preview_path = bundle_dir / f"{file_stem}.gif"
            render_path = bundle_dir / f"{file_stem}.webm"

            js_path.write_text(code, encoding="utf-8")
            html_path.write_text(
                "\n".join(
                    [
                        "<!doctype html>",
                        "<html>",
                        "<head>",
                        "  <meta charset=\"utf-8\">",
                        f"  <title>{label}</title>",
                        "  <style>html, body { margin: 0; background: transparent; overflow: hidden; } #stage { width: 100vw; height: 100vh; position: relative; }</style>",
                        "  <script src=\"https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.1/anime.min.js\"></script>",
                        "</head>",
                        "<body>",
                        "  <div id=\"stage\"></div>",
                        f"  <script src=\"{js_path.name}\"></script>",
                        "</body>",
                        "</html>",
                    ]
                ),
                encoding="utf-8",
            )

            style_profile = self._overlay_style_profile(asset_id, label, code, width, height)
            style_index = int(style_profile["style_index"])

            frames: list[Image.Image] = []
            frame_arrays: list[np.ndarray] = []
            total_frames = max(12, int(round(duration * fps)))
            total_frames = min(total_frames, 96)
            for frame_index in range(total_frames):
                phase = ((frame_index / max(1, total_frames - 1)) * math.tau) + float(style_profile["phase_offset"])
                frame = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
                frame_draw = ImageDraw.Draw(frame)
                if style_index == 0:
                    self._draw_ring_particles(frame_draw, width, height, phase, style_profile)
                elif style_index == 1:
                    self._draw_left_to_right_bars(frame_draw, width, height, phase, style_profile)
                elif style_index == 2:
                    self._draw_pulse_cards(frame_draw, width, height, phase, style_profile)
                else:
                    self._draw_corner_pop(frame_draw, width, height, phase, style_profile)
                frames.append(frame)
                frame_arrays.append(np.array(frame))
            if not frames:
                blank = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
                frames = [blank]
                frame_arrays = [np.array(blank)]
            from moviepy import ImageSequenceClip  # type: ignore[import-untyped]

            sequence_clip = ImageSequenceClip(frame_arrays, fps=max(1.0, float(fps)), with_mask=True)
            try:
                sequence_clip.write_videofile(
                    str(render_path),
                    fps=max(1.0, float(fps)),
                    codec="libvpx-vp9",
                    audio=False,
                    ffmpeg_params=["-pix_fmt", "yuva420p"],
                    logger=None,
                )
            finally:
                close = getattr(sequence_clip, "close", None)
                if callable(close):
                    close()
            frames[0].save(
                preview_path,
                save_all=True,
                append_images=frames[1:],
                duration=max(1, int(round(1000 / max(fps, 1.0)))),
                loop=0,
                disposal=2,
                transparency=0,
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "asset_id": asset_id,
                        "label": label,
                        "width": int(width),
                        "height": int(height),
                        "duration": float(duration),
                        "fps": float(fps),
                        "html": html_path.name,
                        "script": js_path.name,
                        "render": render_path.name,
                        "render_format": "webm",
                        "preview": preview_path.name,
                        "preview_format": "gif",
                        "style_index": style_index,
                        "style_signature": style_profile["signature"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            asset = Asset(
                id=asset_id,
                path=workspace.to_storage_path(render_path),
                source="generated",
                media_type="video",
                duration=float(duration),
                metadata={
                    "generator": "animejs",
                    "transparent": True,
                    "size": [int(width), int(height)],
                    "fps": float(fps),
                    "duration": float(duration),
                    "label": label,
                    "style_index": style_index,
                    "style_signature": style_profile["signature"],
                    "animejs_bundle": {
                        "html_path": workspace.to_storage_path(html_path),
                        "script_path": workspace.to_storage_path(js_path),
                        "manifest_path": workspace.to_storage_path(manifest_path),
                        "render_path": workspace.to_storage_path(render_path),
                        "preview_path": workspace.to_storage_path(preview_path),
                    },
                    "visible_preview": True,
                    "animation_format": "webm",
                    "preview_format": "gif",
                    "render_backend": "python_fallback",
                    "source_hash": hashlib.sha1(code.encode("utf-8")).hexdigest(),
                },
                tags=["overlay", "animejs", "transparent", "animated", f"style_{style_index}"],
            )

            command = AddAssetCommand(asset)
            result = command.execute(project)

            if not result.ok:
                return ToolResult(
                    ok=False,
                    status="error",
                    code=result.code,
                    message=result.message,
                    operation="generate_animejs_overlay_asset",
                    project_id=project.id,
                    project_version=project.version,
                    validation=result.validation,
                    render_state=RenderState(
                        ready=False, blockers=list(result.validation.errors)
                    ),
                    state=result.state,
                    summary=result.message,
                    error=result.message,
                ).to_dict()

            saved_path = self.store.save(project, output_path or project_path)
            report = self.store.validate(project)

            return ToolResult(
                ok=report.passed,
                status="ok" if report.passed else "warn",
                code="asset.generated",
                message="Anime.js overlay asset generated",
                operation="generate_animejs_overlay_asset",
                project_id=project.id,
                project_version=project.version,
                changes=result.changes,
                validation=ValidationSnapshot(
                    passed=report.passed,
                    warnings=[issue.message for issue in report.warnings],
                    errors=[issue.message for issue in report.errors],
                ),
                render_state=RenderState(
                    ready=report.passed, blockers=[issue.code for issue in report.errors]
                ),
                artifacts=[
                    ArtifactRef(type="project", path=str(saved_path)),
                    ArtifactRef(type="video", path=str(render_path), label="overlay_render"),
                    ArtifactRef(type="image", path=str(preview_path), label="overlay_preview"),
                    ArtifactRef(type="html", path=str(html_path), label="animejs_html"),
                    ArtifactRef(type="script", path=str(js_path), label="animejs_script"),
                    ArtifactRef(type="json", path=str(manifest_path), label="animejs_manifest"),
                ],
                state={
                    **result.state,
                    "project_path": str(saved_path),
                    "asset_id": asset_id,
                    "asset_path": workspace.to_storage_path(render_path),
                    "bundle_manifest_path": workspace.to_storage_path(manifest_path),
                    "style_index": style_index,
                    "style_signature": style_profile["signature"],
                },
                payload=project.to_dict(),
                next_actions=["apply_overlay_to_screen"],
                summary=f"Generated Anime.js overlay asset {asset_id}",
            ).to_dict()

    def _draw_ring_particles(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        center_x = int(width * float(style_profile["center_x"]))
        center_y = int(height * float(style_profile["center_y"]))
        ring_color = tuple(style_profile["glow"])
        dot_color = tuple(style_profile["accent"])
        pulse = 0.75 + 0.25 * math.sin(phase)
        orbit_radius = int(style_profile["orbit_radius"])
        for radius in (max(18, int(orbit_radius * 0.45)), max(32, int(orbit_radius * 0.8)), max(48, int(orbit_radius * 1.15))):
            bbox = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
            draw.ellipse(bbox, outline=ring_color, width=max(2, int(round(4 * pulse))))
        dot_count = int(style_profile["dot_count"])
        dot_size = int(style_profile["dot_size"])
        orbit_jitter = int(style_profile["orbit_jitter"])
        for index in range(dot_count):
            angle = (math.tau * index) / float(dot_count) + phase
            distance = orbit_radius + int(orbit_jitter * math.sin(phase * 1.7 + index))
            orbit_x = int(center_x + math.cos(angle) * distance)
            orbit_y = int(center_y + math.sin(angle) * (distance + int(orbit_jitter * math.cos(phase * 1.3 + index))))
            radius = int(dot_size + max(1, dot_size // 2) * (0.5 + 0.5 * math.sin(phase + index)))
            draw.ellipse((orbit_x - radius, orbit_y - radius, orbit_x + radius, orbit_y + radius), fill=dot_color)

    def _draw_left_to_right_bars(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        accent = tuple(style_profile["accent"])
        base_y = int(height * (0.56 + 0.24 * float(style_profile["center_y"])))
        bar_count = int(style_profile["bar_count"])
        bar_height = int(style_profile["bar_height"])
        bar_swing = float(style_profile["bar_swing"])
        for index in range(bar_count):
            bar_w = int(width * (0.08 + 0.06 * (index + 1)))
            bar_h = int(bar_height + bar_height * 0.6 * math.sin(phase + index))
            offset = int((width + 180) * ((index / max(1.0, float(bar_count))) + bar_swing * math.sin(phase * 1.4 + index)))
            left = offset - bar_w
            top = base_y - bar_h // 2 + index * 8
            draw.rounded_rectangle((left, top, left + bar_w, top + bar_h), radius=8, fill=accent)

    def _draw_pulse_cards(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        card_color = tuple(style_profile["accent"])
        glow_color = tuple(style_profile["glow"])
        center_x = int(width * float(style_profile["center_x"]))
        center_y = int(height * float(style_profile["center_y"]))
        scale = (1.0 - float(style_profile["card_scale_swing"])) + float(style_profile["card_scale_swing"]) * math.sin(phase)
        card_w = int(width * float(style_profile["card_width_ratio"]) * max(0.6, scale))
        card_h = int(height * float(style_profile["card_height_ratio"]) * max(0.6, scale))
        draw.rounded_rectangle(
            (center_x - card_w, center_y - card_h, center_x + card_w, center_y + card_h),
            radius=24,
            fill=card_color,
        )
        for radius in (card_w + 20, card_w + 50 + int(style_profile["orbit_jitter"])):
            draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), outline=glow_color, width=4)

    def _draw_corner_pop(self, draw: ImageDraw.ImageDraw, width: int, height: int, phase: float, style_profile: Dict[str, Any]) -> None:
        accent = tuple(style_profile["accent"])
        pop = 0.5 + 0.5 * math.sin(phase)
        size = int(min(width, height) * (float(style_profile["size_ratio"]) + 0.03 * pop))
        point_count = int(style_profile["point_count"])
        point_spread = float(style_profile["point_spread"])
        center_x = float(style_profile["center_x"])
        center_y = float(style_profile["center_y"])
        points: list[tuple[int, int]] = []
        for index in range(point_count):
            angle = phase + (math.tau * index) / max(1, point_count)
            x = int(width * min(0.88, max(0.12, center_x + point_spread * math.cos(angle))))
            y = int(height * min(0.88, max(0.12, center_y + point_spread * math.sin(angle))))
            points.append((x, y))
        for x, y in points:
            draw.ellipse((x - size, y - size, x + size, y + size), fill=accent)
